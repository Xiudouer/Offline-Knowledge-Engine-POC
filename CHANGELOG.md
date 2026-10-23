# Changelog

本项目的显著变更记录在此文件。格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### Added

- GitHub Actions `tests` 工作流：Python 3.12 安装 `requirements.txt` 并运行完整 unittest。

## [1.0.0] - 2026-10-20

### Added

- 完整的单机知识引擎源码：HTTP 服务、浏览器界面、文档解析、分块、pgvector 检索、Ollama 生成和引用守卫。
- 本地 docreader 子进程，支持 UTF-8 TXT/MD/CSV、PDF 文本层和 DOCX 段落/表格文本。
- 700 字符分块、80 字符重叠；PDF 页码与规范化文本字符偏移。
- PostgreSQL/pgvector `vector(1024)`、余弦距离、HNSW 和模型身份绑定。
- 无证据不生成、引用编号守卫、来源片段展示和上传大小/页数/块数限制。
- 仅 internal 网络的 Compose 拓扑、端点 allowlist、无代理/重定向客户端和离线资源校验。
- 30 项源码测试、夹具自检、`live_check.py` 联调/隔离检查，以及 Windows/Linux 启动入口。
- `PREPARE-OFFLINE.md`、`TEST-RESULTS.md`、`RELEASE-INFO.json` 和 `SOURCE-ARTIFACTS.json`。

### Verified

- Windows x64 / CPython 3.12：30 项源码测试通过；夹具 demo 4 项通过。
- 应用代码与 1.0.0 应用镜像逐文件一致；离线资源清单、镜像/模型 digest 已记录。
- 构建机未运行 Docker 实际加载、真实 pgvector 查询、真实 Qwen 生成和运行期外网阻断；目标机必须先运行 `check.bat` / `python run.py check`。

### Notes

- 1.0.0 是 POC，不是生产知识平台，也不提供独立安全审计、合规认证或模型准确率保证。
- `wheels/`、`assets/`、模型、镜像、EXE、真实文档和 `private-state/` 不包含在此源码仓库。

## Repository

- 2026-10-23：在 GitHub 仓库补充完整 1.0.0 源码、测试、脚本、README 与发布元数据。
