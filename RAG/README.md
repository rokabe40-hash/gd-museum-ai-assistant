## 说明：

├── src/museum_rag/                    RAG核心Python源码
├── tests/                             自动化测试
├── data/
│   ├── processed/
│   │   ├── documents.jsonl            3,666篇统一结构文档
│   │   └── chunks.jsonl               3,857个检索文本块
│   ├── cache/
│   │   └── embeddings.sqlite3          Dense和Sparse嵌入结果缓存
│   ├── qdrant/                        Qdrant Local向量索引
│   ├── evaluation/qa_dataset.jsonl    80题评测集
│   └── reports/                       数据审计、清洗和评测报告
├── dist/
│   └── museum_rag-0.1.0-py3-none-any.whl
│                                       可安装的RAG Python包
├── 基本信息.json                      博物馆简介和大事记
├── 参观信息.json                      开放、预约和交通信息
├── 展厅.json                          展厅位置和介绍
├── 展览.json                          当前、常设和往期展览
├── 藏品库.json                        3,730条藏品数据，其中119件精品已增强
├── 设施信息.json                      馆内设施信息
├── pyproject.toml                     项目及依赖配置
├── uv.lock                            依赖版本锁定文件
└── .env.example                       环境变量模板，不含真实密钥


## 功能说明

- 将六类不同结构的JSON转换成统一文档。
- 为119件精品藏品补充详细介绍、别名、特征和关键词。
- 对长文本按数据类型进行切块。
- 使用`qwen3.7-text-embedding`生成1024维Dense向量和Sparse向量。
- 通过`embeddings.sqlite3`复用已经生成的底库向量，避免重建索引时重复调用嵌入API。
- 使用Qdrant Local持久化并执行Dense+Sparse RRF混合检索。
- 提供异步`Retriever`接口供FastAPI调用。
- 使用80题评测集验证召回和拒答效果。

当前交付目录测试结果为`11 passed`；留出集Recall@5为100%，MRR为0.9139。


## 向量文件说明

```text
data/cache/embeddings.sqlite3
└── 嵌入结果缓存；用于复用底库和查询向量，支持低成本重建索引

data/qdrant/collection/museum_chunks_v1/storage.sqlite
└── 正式向量索引；程序执行检索时实际读取
```


