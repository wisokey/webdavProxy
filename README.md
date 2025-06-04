# WebDAV 代理服务

这是一个 Python 实现的 WebDAV 代理服务，它能够：

1. 对外提供标准的 WebDAV 服务接口
2. 将请求转发到另一个后端 WebDAV 服务
3. 支持基本的身份认证 (Basic Authentication)
4. 支持文件无感切割合并上传下载（规避后端文件上传大小限制）

## 功能特性

- 完整支持 WebDAV 协议
- 支持基本身份认证
- 可配置的代理规则
- 简单易用的配置
- 支持文件无感切割上传
- 支持切割文件无感合并下载

## 安装

您可以通过以下几种方式安装和运行此服务：

### 1. 本地直接运行 (推荐用于开发)

```bash
# 安装依赖
pip install -r requirements.txt
```
后续请参考 "[运行](#运行)" 和 "[配置](#配置)" 部分。

### 2. 使用 Docker (推荐用于部署)

请参考 "[使用 Docker 运行](#使用-docker-运行)" 部分。

## 配置

编辑 `config/config.yaml` 文件（从 `config/config.yaml.example` 复制）:

```
# 代理服务器配置
HOST: 0.0.0.0
PORT: 8080
MOUNT_PATH: /dav/
AUTH_USERNAME: user
AUTH_PASSWORD: password

# 后端 WebDAV服务器配置
BACKEND_URL: https://example.com/webdav
BACKEND_USERNAME: backend_user
BACKEND_PASSWORD: backend_password

# 元数据缓存配置
METADATA_CACHE_SIZE: 2000
METADATA_CACHE_TTL: 60

# 日志配置
# 是否将日志写入文件，设置为true开启文件日志，false仅输出到控制台
ENABLE_FILE_LOGGING: false
# 日志级别：DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_LEVEL: INFO
# 日志文件路径（仅在ENABLE_FILE_LOGGING=true时生效）
LOG_FILE: webdav_proxy.log

# 开启文件切割大小,超过该大小的文件将被切割上传到后端，单位为字节,默认为8GB
FILE_MAX_SIZE: 8589934592
```

## 运行

```bash
python main.py
```

## 使用 Docker 运行

本项目支持使用 Docker 进行部署和运行。

### 构建 Docker 镜像 (可选)

如果您希望在本地构建 Docker 镜像，可以在项目根目录下运行以下命令：

```bash
docker build -t webdav-proxy .
```
(请确保 Dockerfile 文件位于项目根目录)

### 运行 Docker 容器

您可以使用以下命令来运行 Docker 容器。请确保您已经准备好了 `config/config.yaml` 文件。

```bash
docker run -d \
  --name my-webdav-proxy \
  -p 8080:8080 \
  -v /path/to/your/config:/app/config \
  webdav-proxy
```

**参数说明:**
- `-d`: 后台运行容器。
- `--name my-webdav-proxy`: 为容器指定一个名称。
- `-p 8080:8080`: 将主机的 8080 端口映射到容器的 8080 端口。您可以根据需要更改主机端口。
- `-v /path/to/your/config:/app/config`: 将您本地的 `config/config.yaml` 文件挂载到容器内的 `/app/config`。**请务必将 `/path/to/your/config` 替换为您的实际配置文件夹路径。**
- `webdav-proxy`: 您在本地构建的 Docker 镜像名称 (例如 `webdav-proxy`)，或者将来从 Docker Hub 等镜像仓库拉取的镜像名称。

### GitHub Actions 自动构建

本项目已配置 GitHub Actions (`.github/workflows/docker-image-build.yaml`)，会在代码推送到特定分支 (例如 `main`) 时自动构建 Docker 镜像。您可以根据需要将其配置为推送到 Docker Hub 或其他容器镜像仓库。

## 使用

运行后，你可以使用任何 WebDAV 客户端连接到 `http://localhost:8080/dav/`，使用配置的用户名和密码进行身份验证。
