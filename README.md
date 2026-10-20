# Offline Knowledge Engine POC

> 本仓库仅发布文档、示例和许可证；不包含应用源码、EXE、模型权重或容器镜像。以下运行说明适用于另行分发的完整离线包，单独克隆此仓库不能启动服务。

基于 WeKnora 本地解析、分块、向量检索和知识问答流程做出的单机参考实现。**Python 应用 + 本地 docreader + PostgreSQL/pgvector + Ollama**，不需要 WeKnora 完整后端、云模型账号、对象存储或外部解析服务。

本包面向数据主权场景的概念验证，不是企业知识平台的完整替代。它包含源代码、浏览器界面、Windows 操作入口、测试与离线资源清单。资源准备情况及实际验证范围，以包内 `RELEASE-INFO.json` 和 `TEST-RESULTS.md` 为准。

## 接收者如何使用

要求 Windows x64 + 已安装并启动的 Docker Desktop **Linux engine**，或 Linux x86-64 + Docker Engine/Compose v2。Windows 入口自带 Python，无需额外安装 Python。模型固定为本地 `qwen3:0.6b` 和 `qwen3-embedding:0.6b`，默认 CPU 推理；建议 16 GB 内存、Docker 可用内存至少 8 GB，磁盘预留至少 20 GB。小模型用于展示闭环，不代表企业任务的准确率。

1. 在没有业务数据的地方解压**整个** ZIP；保持 EXE、`_internal/`、`assets/`、源码和示例目录在一起。
2. 完整离线包已带 `assets/images.tar` 与 `assets/models/`。双击 `start.bat`：校验离线资源、加载本地镜像、生成随机访问令牌/数据库密码、启动隔离的三个容器。首次加载较慢，不会 `docker pull` 或自动下载模型。
3. 打开 **http://127.0.0.1:18787**，从 `private-state/access-token.txt` 复制访问令牌，点击连接。
4. 先上传 `examples/backup-policy.md`，再问“示例制度的备份周期和保留时间是什么？”。回答下方可展开来源、页码/文本位置及片段。
5. 点击“移除”只删除索引记录；原始本地文件不受影响。双击 `stop.bat` 停止本实例，数据库卷保留。

`demo.bat` 是**夹具自检**：验证本地解析、来源位置与引用约束，不调用真正的 Ollama 或 pgvector。要运行完整链路必须使用 start，并满足 Docker 和离线资源要求。

首次初始化会创建不同的随机凭据和独立 Compose project 名称，避免不同解压副本共用知识库。所有容器只加入一个 `internal: true` 网络，只有应用入口映射到宿主 `127.0.0.1`；数据库和 Ollama 不开放宿主端口。不要把该 HTTP 入口改成公网或内网共享服务后继续沿用此单用户 POC 的信任模型。

## “数据不出内网”如何落实

本版把**运行期**与**资源准备期**分开。运行期没有云模型适配器、网页抓取、远程文档解析、模型拉取 API、外部字体、统计脚本或 CDN。

| 层 | 本版控制 |
|---|---|
| 容器网络 | 三个服务仅加入 internal 网络；无 host 网络、Docker socket 或额外外网网络；自定义 DNS 回退指向容器自身 loopback；显式清空 HTTP/HTTPS/ALL_PROXY，并设置 NO_PROXY=* |
| 模型 | Ollama 设置 `OLLAMA_NO_CLOUD=1`；只用两个预置本地模型；启动 `pull_policy: never` / `--pull never --no-build` |
| 应用 HTTP 客户端 | 不读取系统代理，不跟随重定向；只允许已知本地服务名/loopback，解析后必须是批准私网地址；不能传入任意模型 URL |
| docreader | 仅处理上传的字节和文件名，不抓取 URL、不跟随外部链接、不运行宏、不调用云 OCR；独立子进程，时间/内存/文件大小限制 |
| 浏览器 | 访问令牌仅在当前页面内存中；同源请求、Host 校验、无 CORS 放行；动态文档内容用 textContent 显示，CSP 限制脚本和连接来源 |
| 日志 | 应用不记文件内容、问题、回答、Token 或完整异常；Postgres 禁止记录 SQL 参数值，容器日志限额；Ollama debug 关闭 |

这些是组件内的控制，**不等于对接收者整台电脑、Docker 守护进程或运维管理员的网络隔离证明**。Docker/操作系统需要由接收者事先部署并按组织要求管控出口。内网验收时，运行 `scripts/live_check.py`，检查真实入库/模型调用、容器仅接内部网络、应用外部 TCP/DNS 不可达；同时使用组织防火墙/流量审计确认出口。构建机未完成的验证会明确记录，不会用夹具测试代替。

## 支持的文档与边界

- UTF-8 TXT/MD/CSV；PDF 的可提取文本层；DOCX 主文档的段落/表格文本。
- 单文件最多 20 MiB，PDF 最多 300 页，提取文本最多 200 万字符；单文档最多 5000 块，单实例最多约 20000 块。
- 700 字符分块，80 字符重叠；PDF 保留页码，来源位置是规范化文本的 Unicode 字符偏移，end 为开区间。
- 扫描 PDF、加密 PDF、图片 OCR、PPT/XLS、网页、附件图片、脚注、页眉页脚、复杂 DOCX 版式还原不在范围内。CSV 当前作为文本处理。
- 上传内容解析后保存文本块和向量；**不保存原始 PDF/DOCX 字节供下载**。原文件由用户自行保管，来源页码/片段用于对照。

入库顺序：校验本地模型身份 → 解析 → 分块 → 批量 embedding → 数据库事务提交。解析或 embedding 失败不会留下半份文档。文档 ID 由文件名与内容共同计算，同名同内容重复上传不会重复建立记录；同名不同内容会作为新文档，需要用户移除旧版本。

## 检索与回答

pgvector `vector(1024)`，余弦距离 `<=>`，HNSW 索引；模型、digest 和维度记录在索引元数据中。模型变化时拒绝继续混用旧向量，需在保留原文件的前提下建立新实例重新入库。

检索取最多 12 个候选，余弦分数低于 0.2 不进入回答；对这些候选做轻量关键词重排，再取最多 5 段、总计最多 5000 字符。0.2 是 POC 初始门槛，不是经过业务标注集校准的概率。没有来源时直接返回证据不足，不调用生成模型。

生成阶段只把问题和选出的片段送到本地 Ollama。文档里的命令、角色声明和 URL 被当作不可信数据，不配套任何执行工具。模型回答必须使用现有的 `[S1]` 来源编号；缺少引用或出现不存在的编号时，界面提示查看原始检索片段。**编号合法不证明回答受到证据支持**，小模型可能误解或遗漏内容，请人工核对。

## 命令行与源码

```powershell
.\OfflineKnowledgeEngine.exe demo
.\OfflineKnowledgeEngine.exe verify
.\OfflineKnowledgeEngine.exe start
.\OfflineKnowledgeEngine.exe check
.\OfflineKnowledgeEngine.exe status
.\OfflineKnowledgeEngine.exe stop
```

源码入口：`python run.py ...`；Linux 可 `sh start.sh`，操作入口只用 Python 标准库。真正的应用和 docreader 在 Linux 容器内运行，依赖固定版本见 `requirements.txt`。

```sh
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
# 先启动完整服务，再运行真实联调/隔离检查
python scripts/live_check.py
```

未联网的目标机不应执行 pip install；完整离线镜像已包含依赖。Windows 接收者启动后可直接双击 `check.bat` 运行真实联调/隔离检查，无需另装 Python。脚本只针对本包生成的 Compose project 操作，不会清理其他项目、删除卷或自动改防火墙。

## 私有状态和转发

把**原始 ZIP 及其 SHA-256 文件**发给别人。不要重新打包已经运行过的目录。

- `private-state/` 含访问令牌、数据库密码、实例 Compose 配置及初始化 SQL，不能转发。POSIX 目录 0700；Windows 继承父目录 ACL，应放在受控用户目录。
- 数据库在该实例的 Docker named volume 内，包含提取文本、文件名、embedding 与时间元数据。它没有应用层加密，宿主/Docker 管理员可以访问；按组织要求做磁盘加密、访问控制和备份。
- `assets/models/` 只装公共模型文件并只读挂载；不会把宿主的整个 `.ollama/` 或其中的私钥打包。
- 本版没有多用户 RBAC、远程登录、TLS 共享入口、审计合规、备份调度或集群支持。需要这些能力时在 POC 之外单独集成。
- stop 保留数据。若要销毁旧知识库，由有权限的用户先备份、确认对应实例，再手动处理其 Docker 卷；本包没有一键删库命令。

## 离线资源准备与溯源

完整离线包的镜像和模型 digest 在 `SOURCE-ARTIFACTS.json` / `assets/ASSETS.json` 中。运行前校验大小及 SHA-256，再检查本地镜像 ID，避免静默换成同名镜像或在线拉取。

需要升级/重新准备资源时，只在**没有业务数据的联网中转机**运行 `scripts/prepare_online.py`；它会显式下载官方依赖、镜像、模型并导出离线资源。它不会在 start 时被自动调用。详见 `PREPARE-OFFLINE.md`。

本版的 docreader 和应用是独立精简实现，不兼容 WeKnora 的 gRPC/数据库结构。来源对应见 `UPSTREAM.md`。应用代码 MIT；上游、依赖和模型许可证见 `licenses/` 与 `THIRD-PARTY.md`。本项目不是腾讯、Ollama 或 PostgreSQL 官方发行版。
