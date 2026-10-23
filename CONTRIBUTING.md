# Contributing

OfflineKnowledgeEngine 是一个面向数据主权场景的单机 POC。贡献应保持 **离线优先、最小依赖、默认拒绝外部连接** 的设计，不要把项目扩展成多租户或公网服务。

## 开发环境

- Python 3.12+
- 源码测试：`python -m pip install -r requirements.txt`
- 完整联调：Docker Desktop Linux engine 或 Linux Docker Engine、Compose v2，以及按 `PREPARE-OFFLINE.md` 准备的本地资源

```sh
python run.py demo
python -m unittest discover -s tests -v
# 完整栈启动后
python scripts/live_check.py
```

`demo` 和单元测试使用夹具，不要求真实 Ollama 或 pgvector；`live_check.py` 才会验证真实入库、模型调用和网络隔离。

## 修改准则

- 运行期不得引入云模型适配器、网页抓取、远程文档解析、模型拉取、CDN、遥测或外部字体。
- 不要添加任意模型 URL、代理跟随、重定向跟随或未校验的远端地址；HTTP 客户端必须继续限制在批准的本地/私网端点。
- 文档解析只处理上传的字节和文件名；不要执行宏、外部链接、云 OCR 或不受限的解析器。
- 不记录文件内容、问题、回答、Token、完整异常或 SQL 参数值。
- 修改解析、分块、检索、引用守卫或网络策略时，必须补充 `tests/` 中的测试；涉及数据库或容器的改动需说明如何用 `live_check.py` 验证。
- 更新用户可见行为时同步修改 README、`TEST-RESULTS.md` 和 `CHANGELOG.md`。
- **不要提交** `private-state/`、`assets/`、`wheels/`、模型权重、镜像 tar、EXE、ZIP、数据库、证书或任何真实文档与凭据。这些路径已在 `.gitignore` 中排除。

## 提交与 Pull Request

1. 从最新 `main` 创建分支，一个提交只做一类改动。
2. 提交信息说明动机、行为变化和安全影响。
3. PR 描述包含：测试命令、是否运行过 `live_check.py`、未覆盖的环境或边界。
4. 确保 `python -m unittest discover -s tests -v` 通过；如果依赖缺失导致测试跳过，请明确说明。
5. 不要在 PR 中附加真实业务文档、访问令牌、数据库导出或容器日志。

## 安全报告

请不要在公开 Issue 中粘贴访问令牌、数据库密码、私钥、真实文档内容或可利用细节。先使用仓库的私密安全报告渠道联系维护者；如果不可用，只发一个不含敏感内容的最小说明。

## 许可证

提交即表示你同意以本仓库的 MIT 许可证（见 [LICENSE](LICENSE)）发布你的贡献。上游与第三方声明见 [THIRD-PARTY.md](THIRD-PARTY.md) 和 [UPSTREAM.md](UPSTREAM.md)。
