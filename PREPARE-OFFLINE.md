# 准备与验收离线交付

运行期不能下载资源。完整包必须包含 `assets/images.tar`、`assets/models/`、`assets/ASSETS.json`。

## 联网中转机重新准备

使用没有真实文档、问题或业务数据库的专用目录；Python 3.12+、Docker Linux engine、Compose v2、至少 20 GB 空间。

```sh
python scripts/prepare_online.py
```

仅此步骤需要公网访问官方 PyPI、Docker Hub 和 Ollama 模型仓库。脚本不读取用户文档、不挂载用户 HOME、Docker socket 或已有知识库。目标 images.tar 是 Linux amd64 镜像，适用于 Windows Docker Desktop Linux 模式和 Linux x86-64。

若 assets 已存在，脚本拒绝覆盖。升级时使用新副本，保留已有实例和数据。脚本创建专用临时模型准备容器，退出后只移除此容器；不碰其他容器或卷。

该通用脚本默认保留官方 Ollama 镜像的全部运行库，包可能较大。本次交付如使用 CPU 精简派生镜像，会在 SOURCE-ARTIFACTS.json 中明确记录；模型权重不被修改。

## 带入内网

1. 转移原始发布包和独立获取的 SHA-256 校验值。哈希用于完整性检查，不是签名/发布者身份认证。
2. 在目标机断网或阻断公网出口后运行 start，确认未发生 pull/build/pip/model 下载。
3. 使用示例文档完成入库、检索、问答和来源核对，再运行 `check.bat` 或 `OfflineKnowledgeEngine.exe check`。也可用 `python scripts/live_check.py`；依赖仅为标准库和 Docker CLI。
4. 结合宿主防火墙和抓包/网关日志确认没有不允许的流量。检查所有三个容器仅连接同一个 internal 网络，未增挂桥接外网网络、host network 或 Docker socket。
5. 验收通过后再放入真实数据。

live_check 只使用随包的虚构制度文本；外网探测只尝试建立 TCP 连接和解析固定公共域名，不发送文档内容。必须拒绝这些探测才算该检查通过。网络测试失败时先修复部署，不能把“能回答问题”当成已满足隔离。

Docker 无法访问、镜像缺失、模型缺失、密钥配置缺失、向量维度/模型身份改变时均停止或报错，不回退到云服务。不能运行 Docker 的环境仍可执行 demo 夹具自检，但它不是完整知识引擎运行证明。
