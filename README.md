# OfflineKnowledgeEngine · 离线知识引擎 POC

基于 WeKnora 本地解析、分块、向量检索和知识问答流程做出的单机参考实现：**Python 应用 + 本地 docreader + PostgreSQL/pgvector + Ollama**，不需要 WeKnora 完整后端、云模型账号、对象存储或外部解析服务。

本仓库包含 **1.0.0 的完整应用源码、测试、运行/构建脚本和文档**，应用代码与 1.0.0 应用镜像逐文件一致。

> **仓库范围**：不包含 `wheels/`、`assets/`（Docker 镜像 tar、模型权重）、PyInstaller EXE、容器镜像或任何真实文档与凭据。完整离线交付包需按 [PREPARE-OFFLINE.md](PREPARE-OFFLINE.md) 在联网中转机另行准备；目标机不应执行 `pip install` 或在线拉取。

## 仓库结构

| 路径 | 内容 |
|---|---|
| `offlineknowledge/` | 应用源码：HTTP 服务、docreader、检索/回答编排、pgvector 存储、本地网络策略、CLI 与自检 |
| `offlineknowledge/web/` | 浏览器界面（无外部字体、CDN 或统计脚本） |
| `tests/` | 30 项源码测试：解析、分块、检索边界、HTTP、来源编号与配置检查 |
| `scripts/` | `prepare_online.py` 资源准备、`build_release.py` 发布打包、`live_check.py` 真实联调/隔离检查 |
| `examples/` | 虚构制度文档与集成示例 |
| `licenses/` | WeKnora 上游许可证 |
| `Dockerfile`、`.dockerignore` | Linux 应用镜像构建定义（依赖离线 wheels） |
| `requirements.txt`、`run.py` | Python 依赖与源码入口 |
| `build-windows.ps1` | Windows 便携包构建（PyInstaller + 发布打包） |
| `start.bat` / `start.sh` / `stop.bat` / `check.bat` / `demo.bat` | 运行与检查入口 |
| `PREPARE-OFFLINE.md` | 离线资源准备与内网验收流程 |
| `TEST-RESULTS.md` | 1.0.0 测试与未完成验证记录 |
| `CONTRIBUTING.md` / `CHANGELOG.md` | 贡献流程与版本记录 |
| `RELEASE-INFO.json` / `SOURCE-ARTIFACTS.json` | 1.0.0 发布元数据、镜像与模型 digest |

## 快速开始

### 1. 夹具自检（不需要 Docker 或模型）

```sh
python -m pip install -r requirements.txt
python run.py demo
```

`demo` 验证本地解析、来源位置与引用约束，使用确定性夹具，不调用 Ollama 或 pgvector；它不能证明完整知识引擎链路可用。

### 2. 运行源码测试

```sh
python -m unittest discover -s tests -v
```

测试覆盖 TXT/MD/CSV、PDF/DOCX 文本解析、空/扫描 PDF 拒绝、路径与大小限制、字符偏移、向量形状、端点策略、来源编号守卫、HTTP Host/Origin/Token 检查和 SQL 参数化等。PostgreSQL/pgvector 事务、真实模型生成和容器隔离属于 `live_check.py` 的联调范围。

### 3. 运行完整离线栈

在**没有业务数据**的联网中转机准备资源（需要 Docker Desktop Linux engine 或 Linux Docker Engine、Compose v2，至少 20 GB 空间）：

```sh
python scripts/prepare_online.py
```

该步骤会下载固定的 Python wheels、三个应用镜像和两个 Qwen3 模型，写入 `assets/`；不会读取用户文档或挂载用户 HOME。随后在目标机：

```sh
python run.py verify     # 校验 assets 清单、大小、SHA-256 与镜像 ID
python run.py start      # 加载镜像，生成随机凭据，启动三个隔离容器
python run.py check      # 真实入库、模型调用、内部网络与外部不可达检查
python run.py status
python run.py stop       # 停止实例，保留数据库卷
```

启动后打开 **http://127.0.0.1:18787**，从 `private-state/access-token.txt` 复制访问令牌。先上传 `examples/backup-policy.md`，再问“示例制度的备份周期和保留时间是什么？”。

> `private-state/` 含访问令牌、数据库密码、Compose 配置和初始化 SQL，已在 `.gitignore` 中排除，不能提交或转发。数据库卷包含提取文本、文件名、embedding 与时间元数据，没有应用层加密。

## 安全设计

本版把**运行期**与**资源准备期**分开。运行期没有云模型适配器、网页抓取、远程文档解析、模型拉取 API、外部字体、统计脚本或 CDN。

- **容器网络**：三个服务仅加入 `internal: true` 网络；无 host 网络、Docker socket 或额外外网网络；显式清空 `HTTP_PROXY`/`HTTPS_PROXY`/`ALL_PROXY`，设置 `NO_PROXY=*`。
- **模型**：Ollama 设置 `OLLAMA_NO_CLOUD=1`；只使用两个预置本地模型；启动使用 `pull_policy: never` / `--pull never --no-build`。
- **应用 HTTP 客户端**：不读取系统代理、不跟随重定向，只允许已知本地服务名/loopback，解析后必须是批准私网地址；不能传入任意模型 URL。
- **docreader**：只处理上传的字节和文件名，不抓取 URL、不跟随外部链接、不运行宏、不调用云 OCR；独立子进程，有时间、内存和文件大小限制。
- **浏览器**：访问令牌只保存在当前页面内存；同源请求、Host 校验、无 CORS 放行；动态内容用 `textContent` 显示，CSP 限制脚本和连接来源。
- **日志**：应用不记录文件内容、问题、回答、Token 或完整异常；Postgres 关闭 SQL 参数值记录，容器日志限额，Ollama debug 关闭。

这些是组件内的控制，**不等于对整台电脑、Docker 守护进程或运维管理员的网络隔离证明**。Docker/操作系统需由接收者部署并按组织要求管控出口；验收时同时检查 `scripts/live_check.py` 结果和防火墙/流量审计。

## 支持的文档与边界

- UTF-8 TXT/MD/CSV；PDF 可提取文本层；DOCX 主文档段落/表格文本。
- 单文件最多 20 MiB，PDF 最多 300 页，提取文本最多 200 万字符；单文档最多 5000 块，单实例最多约 20000 块。
- 700 字符分块、80 字符重叠；PDF 保留页码，来源位置为规范化文本的 Unicode 字符偏移，`end` 为开区间。
- 扫描 PDF、加密 PDF、图片 OCR、PPT/XLS、网页、附件图片、脚注、页眉页脚、复杂 DOCX 版式还原不在范围内；CSV 当前按文本处理。
- 不保存原始 PDF/DOCX 字节供下载；原文件由用户保管，来源页码/片段用于对照。
- pgvector `vector(1024)`、余弦距离 `<=>`、HNSW；模型变化时拒绝混用旧向量。

检索取最多 12 个候选，余弦分数低于 0.2 不进入回答，再经轻量关键词重排取最多 5 段、总计 5000 字符。没有来源时直接返回证据不足，不调用生成模型。生成回答必须使用现有的 `[S1]` 来源编号；编号合法不证明回答受到证据支持，小模型可能误解或遗漏，需要人工核对。

## 版本、验证与许可

- 版本：`1.0.0`，构建日期 `2026-10-20`；镜像和模型 digest 见 [SOURCE-ARTIFACTS.json](SOURCE-ARTIFACTS.json)。
- 原始构建记录：[RELEASE-INFO.json](RELEASE-INFO.json)、[TEST-RESULTS.md](TEST-RESULTS.md)。
- 源码测试 30 项通过；夹具 demo 4 项通过。原始构建机未完成 Docker 实际加载、真实 pgvector 查询、真实 Qwen 生成和运行期外网阻断验证，因此**在放入真实文档前必须运行 `check.bat` / `python run.py check`**。
- 这不是独立安全审计、合规认证、模型准确率评测或生产就绪证明。小模型仅用于展示闭环。
- 应用代码使用 MIT 许可证（见 [LICENSE](LICENSE)）；WeKnora 设计参考与上游许可证见 [UPSTREAM.md](UPSTREAM.md) 和 [licenses/WeKnora-LICENSE.txt](licenses/WeKnora-LICENSE.txt)；第三方组件说明见 [THIRD-PARTY.md](THIRD-PARTY.md)。
- 贡献流程见 [CONTRIBUTING.md](CONTRIBUTING.md)，版本记录见 [CHANGELOG.md](CHANGELOG.md)。
- 本项目不是腾讯、Ollama 或 PostgreSQL 官方发行版，也不兼容 WeKnora 的 gRPC API、文件服务或数据库迁移。
