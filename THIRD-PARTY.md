# 第三方组件与来源说明

本仓库只包含本项目自有源码、测试、脚本和文档，**不包含** Python wheels、模型权重、容器镜像、PyInstaller EXE 或任何第三方许可证全文（`licenses/WeKnora-LICENSE.txt` 除外）。完整离线包会随附固定的第三方构件；其版本与 digest 见 [SOURCE-ARTIFACTS.json](SOURCE-ARTIFACTS.json)。

## 设计与上游来源

本项目的解析、分块、向量检索和问答编排参考 Tencent/WeKnora 的公开源代码，固定提交与精简范围见 [UPSTREAM.md](UPSTREAM.md)。WeKnora 使用 MIT 许可证，许可证原文保留于 [licenses/WeKnora-LICENSE.txt](licenses/WeKnora-LICENSE.txt)。本项目是独立实现，不是腾讯或 WeKnora 官方发行版，也不代表上游背书。

本项目自有源码、测试、脚本和文档使用 MIT 许可证，见 [LICENSE](LICENSE)。

## 完整离线栈使用的第三方组件

| 组件 | 版本/来源 | 许可证 |
|---|---|---|
| Python | 3.12（`python:3.12-slim-bookworm` 基础镜像） | PSF-2.0 |
| psycopg | 3.3.6（`psycopg[binary]`） | LGPL-3.0；二进制 wheel 内含的 libpq 使用 PostgreSQL License |
| pypdf | 6.21.1 | BSD-3-Clause |
| typing_extensions | 4.16.0 | PSF-2.0 |
| tzdata | 2026.5 | Apache-2.0 |
| PostgreSQL / pgvector | 16 / `pgvector/pgvector:pg16` | PostgreSQL License |
| Ollama | `ollama/ollama` 官方镜像（CPU 运行库） | MIT |
| Qwen3 / Qwen3-Embedding | 0.6B 本地模型 | Apache-2.0 |

Docker 基础镜像和模型的具体 digest 记录在 `SOURCE-ARTIFACTS.json`。各第三方组件的完整许可证文本由其上游发行物提供；完整离线包按 `assets/ASSETS.json` 校验后分发，不在本仓库重复收录。

## 使用边界

本项目不修改上述第三方组件的许可证，也不对其作任何担保。再分发完整离线包时，接收者应同时保留各组件随附的许可证与版权声明。Ollama、PostgreSQL、pgvector、Qwen 及其他名称和商标归各自权利人所有。
