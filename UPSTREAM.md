# WeKnora 来源和精简范围

参考 [Tencent/WeKnora](https://github.com/Tencent/WeKnora)，固定提交
`2fbfb4471581cd5e7d731bc7a2d443fe7d8e95b5`（0.8.3）。基于公开源代码的结构分析，独立用 Python 实现单机 POC。

| 上游固定源码 | 对应思路 | 本版 |
|---|---|---|
| `docreader/parser/base_parser.py` | 文件字节解析为文本，其他阶段分离 | `offlineknowledge/docreader.py`，仅本地文件，不包含网络 parser、OCR 或 VLM |
| `docreader/parser/source_locator.py`、`docreader/source_wire.py` | 文本区间映射回文件位置 | 页码 + 文本字符偏移，未移植 bbox/版式重建算法 |
| `internal/application/service/knowledge_process.go`、`chunk.go` | 解析、分块、向量化、入库 | 同步的有界单机 pipeline；事务入库，无任务队列 |
| `internal/models/embedding/ollama.go` | 本地批量 embeddings | `/api/embed`，维度检查、禁止静默截断、记录模型 digest；缺失模型不自动拉取 |
| `internal/application/repository/retriever/postgres/repository.go` | PostgreSQL/pgvector 检索 | 独立 schema、vector(1024)、余弦候选和 HNSW；不复用上游表结构 |
| `internal/application/service/knowledgebase_search.go` | 检索、候选整理 | 余弦门槛与轻量关键词重排，不包含跨库融合、复杂 reranker |
| `internal/application/service/session_knowledge_qa.go`、`internal/models/chat/ollama.go` | 把检索证据交给模型回答 | 仅本地 Chat API，有来源编号守卫；无工具执行或远程图片解析 |

没有移植 Go 企业后端、租户、IAM、RAG 全部算子、沙箱、IM、连接器、远程 URL 导入、网络搜索、S3 或云模型。
不是 WeKnora 官方 Lite 发行版，也不兼容其 gRPC API、文件服务、数据库迁移或评测结果。

本版额外的内部 Docker 网络、端点 allowlist、无代理/重定向客户端、模型身份绑定和离线资源清单是 POC 的设计选择，不能归因于上游默认行为。

上游完整 LICENSE 保存在 `licenses/WeKnora-LICENSE.txt`。

原始技术资料：

- [Ollama embed](https://docs.ollama.com/api/embed)
- [Ollama local-only configuration](https://docs.ollama.com/faq#how-do-i-disable-ollamas-cloud-features)
- [pgvector](https://github.com/pgvector/pgvector)
- [Docker Compose internal networks](https://docs.docker.com/reference/compose-file/networks/#internal)
- [psycopg installation](https://www.psycopg.org/psycopg3/docs/basic/install.html)
