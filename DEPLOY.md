# 云端部署手册（单机 Docker，演示 / 正式上线通用）

目标：把「后端 + Neo4j + Qdrant」整体部署到阿里云轻量服务器，用一个公网链接对外提供服务。

- 不需要域名 / ICP 备案 / HTTPS（演示阶段）。若后续要正式上线 + 小程序，再补备案与域名。
- 全程只需在【阿里云控制台】【本机终端】【服务器 SSH】三处操作。

---

## 第 1 步 采购服务器（阿里云控制台，约 10 分钟）

1. 控制台 → 轻量应用服务器 → 创建。
2. 配置：
   - 地域：**华南（广州）**（离广东省博物馆近，延迟低）
   - 镜像/系统：**Ubuntu 22.04**
   - 套餐：**2 核 4G** 起（Neo4j 启动需 1~2G 内存，2G 套餐跑不动整套）
3. 设置 root 密码（或创建密钥对），记录**公网 IP**。
4. 控制台「防火墙」→ 添加规则：**放行 TCP 8000**（默认只有 22/80/443，8000 必须手动加）。
5. （可选）先把镜像构建 / 调试做完再买服务器，避免按量计费空转。

---

## 第 2 步 本地准备（本机，一次性）

### 2.1 准备云端 `.env`

在项目根目录复制 `.env.example` 为 `.env`，填入（**根 `.env` 填全即可，云端 `RAG/.env` 可不建**，compose 会把根 `.env` 注入进程环境、被 RAG Settings 读取）：

| 变量 | 必填 | 说明 |
|---|---|---|
| `DEEPSEEK_KEY` | ✅ | LLM 密钥 |
| `NEO4J_PASSWORD` | ✅ | 云端 Neo4j 密码，任意自定（compose 强制必填） |
| `DASHSCOPE_API_KEY` | ✅ | 嵌入服务密钥 |
| `DASHSCOPE_BASE_URL` 或 `DASHSCOPE_WORKSPACE_ID` | ✅ | 嵌入 endpoint（留 BASE_URL 或填 Workspace ID 均可） |
| `CORS_ORIGINS` | ⭕ | 后端托管页面可留 `*`；独立前端时才填前端域名 |
| `API_ACCESS_KEYS` | ✅ 建议 | 逗号分隔访问密钥，防公网 IP 被扫描消耗付费 token |
| `RATE_LIMIT_MAX` / `RATE_LIMIT_WINDOW_SECONDS` | ⭕ | 保持默认 60/60 |
| `TRUST_PROXY_XFF` | ⭕ | 单机直连保持 `0` |

> `.env` 含密钥，**绝不要**随代码打包 / 进 git / 进镜像。

### 2.2 打包代码（排除大数据与密钥）

> ⚠️ `展览.json` 绝不能排除：Neo4j 导入（`import_to_neo4j.py`）与 RAG 向量化（`normalize.py`）都要读它，`RAG/` 与 `Neo4j/广东省博物馆数据/` 两处都缺一不可。

```bash
tar --exclude='.git' \
    --exclude='.claude' \
    --exclude='.vscode' \
    --exclude='.github' \
    --exclude='.env' \
    --exclude='RAG/.env' \
    --exclude='RAG/data' \
    --exclude='RAG/dist' \
    --exclude='RAG/.pytest_cache' \
    --exclude='tests' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.pytest_cache' \
    --exclude='*.egg-info' \
    --exclude='Neo4j/广东省博物馆数据/藏品总目.json' \
    --exclude='Neo4j/具身智能实验室.dump' \
    --exclude='Neo4j/_test_out.txt' \
    --exclude='build_metadata.py' \
    --exclude='clean_metadata.py' \
    --exclude='metadata_mapping.json' \
    --exclude='metadata_dead_letter.json' \
    --exclude='duplicate_names.txt' \
    --exclude='有详细介绍的藏品.json' \
    --exclude='藏品总目.json' \
    --exclude='藏品库 - 补充.json' \
    --exclude='museum_deploy.tar.gz' \
    -czf museum_deploy.tar.gz .
```

### 2.3 准备 embedding 缓存（复用，省去云端重新调嵌入 API）

本地文件 `RAG/data/cache/embeddings.sqlite3`（约 119 MB）是文档向量缓存。上传到服务器后，云端跑 `museum-rag index` 会**全部命中缓存、零嵌入 API 调用**。若不带它，云端会重新调用 DashScope 嵌入（耗时数分钟~半小时 + 少量费用），功能不受影响。

---

## 第 3 步 服务器初始化（SSH）

### 3.1 安装 Docker + compose

```bash
curl -fsSL https://get.docker.com | sh
systemctl enable --now docker
docker compose version
```

> 国内网络若 `get.docker.com` 超时，改用阿里云镜像源安装（搜「阿里云 Docker 安装脚本镜像」）。

### 3.2 上传代码包、缓存与 .env

本机（PowerShell / 终端）执行，`<IP>` 换成公网 IP：

```bash
scp museum_deploy.tar.gz root@<IP>:~/
scp RAG/data/cache/embeddings.sqlite3 root@<IP>:~/embeddings.sqlite3
```

### 3.3 解压 + 放配置文件

```bash
sudo mkdir -p /srv/museum
cd ~ && sudo tar -xzf museum_deploy.tar.gz -C /srv/museum
cd /srv/museum

# 创建 .env（模板 + 填入密钥）
sudo cp .env.example .env
sudo nano .env        # 填 DEEPSEEK_KEY / NEO4J_PASSWORD / DASHSCOPE_* / API_ACCESS_KEYS

# 放置 embedding 缓存，并让 app 用户（uid 1000）可读写
sudo mkdir -p RAG/data/cache
sudo mv ~/embeddings.sqlite3 RAG/data/cache/embeddings.sqlite3
sudo chown -R 1000:1000 RAG/data/cache
```

> `chown 1000` 关键：镜像以非 root（uid 1000）运行，缓存文件必须是该用户可写，否则 `sqlite3` 只读连接会报错。

---

## 第 4 步 数据迁移（云端只跑一次）

```bash
# 4.1 构建镜像（首次拉依赖，国内网络需耐心几分钟）
docker compose build

# 4.2 只起数据服务，等 Neo4j 健康
docker compose up -d neo4j qdrant
docker compose ps        # 等到 neo4j 显示 (healthy)

# 4.3 导入 Neo4j 图谱（--user 0：以 root 跑，避免 /app 只读）
docker compose run --rm --user 0 app python Neo4j/import_to_neo4j.py

# 4.4 构建 RAG 向量库（复用挂载的缓存，命中后不调嵌入 API）
docker compose run --rm --user 0 app sh -c "museum-rag normalize && museum-rag chunk && museum-rag index"
```

> `--user 0` 一次性迁移以 root 执行；日常运行的 app 容器仍是非 root（Dockerfile 的 `USER 1000`）。

---

## 第 5 步 启动后端并验证

```bash
docker compose up -d app
sleep 10
curl -s http://localhost:8000/health        # 期望 {"status":"ok"}

curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <你的API_ACCESS_KEYS>" \
  -d '{"query":"端砚是什么年代的？"}'
```

若返回 `answer`，即全部打通。

---

## 第 6 步 出链接 + 安全收敛

给老师（或前端开发）的链接：

- 聊天接口：`http://<公网IP>:8000/chat`
- Swagger 调试页：`http://<公网IP>:8000/docs`
- 以后托管前端页面后，`http://<公网IP>:8000/` 即完整产品

安全：

- 阿里云防火墙**只放行 22 + 8000**，Neo4j（7687）/ Qdrant（6333）端口不对外（compose 已只暴露 app 端口）。
- `API_ACCESS_KEYS` 必须设置：公网 IP 会被扫描器探测，未鉴权会消耗你的 DeepSeek/DashScope 付费 token。
- 演示结束若不再用，**释放服务器**（轻量应用服务器按量/月付可随时释放，避免持续计费）。

---

## 常见问题

- **`museum-rag index` 仍在调嵌入 API（缓存未命中）**：确认 `CACHE_PATH` 生效——compose 已挂载 `./RAG/data/cache:/cache` 并设 `CACHE_PATH=/cache/embeddings.sqlite3`；本地缓存若由不同 `embedding_model`/维度生成则 key 不匹配，需重建。功能不受影响，只是多花时间。
- **app 起不来 / `neo4j` 不健康**：`docker compose logs neo4j` 看日志；常见是 `NEO4J_PASSWORD` 未设置或内存不足（需 ≥4G）。
- **`/chat` 返回 401**：`API_ACCESS_KEYS` 已设置但请求没带 `X-API-Key`，或 key 不匹配。
- **Windows 本地集成测试报 `Storage folder already accessed`**：Qdrant 本地库文件锁，先停掉开发服务器再跑。
