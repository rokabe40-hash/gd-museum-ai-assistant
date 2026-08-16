# ============================================================
# 广东省博物馆讲解 AI 后端 生产镜像
# Gunicorn 多进程 + Uvicorn worker 榨干多核性能
# ============================================================

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    # 查询向量缓存写入 /tmp（/app 归属 root 只读，非 root 运行必需）
    CACHE_PATH=/tmp/embeddings.sqlite3

WORKDIR /app

# ── 依赖层（利用 Docker 层缓存）──────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── RAG 子项目（可编辑安装，勿装 whl 否则读不到配置/数据）─
COPY RAG/pyproject.toml RAG/README.md RAG/src ./RAG/
COPY RAG/*.json ./RAG/
RUN pip install --no-cache-dir -e ./RAG

# ── 应用代码与运行时数据 ─────────────────────────────
COPY main.py faq_builder.py requirements.txt ./
COPY Neo4j/museum_graph.py Neo4j/import_to_neo4j.py ./Neo4j/
COPY Neo4j/广东省博物馆数据 ./Neo4j/广东省博物馆数据
COPY 基本信息.json 参观信息.json 设施信息.json ./

# ── 非 root 运行，降低提权风险 ───────────────────────
RUN useradd --create-home --uid 1000 appuser
USER 1000

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"

CMD ["gunicorn", "main:app", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "-b", "0.0.0.0:8000"]
