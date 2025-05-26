# WebDAV 代理服务

这是一个 Python 实现的 WebDAV 代理服务，它能够：

1. 对外提供标准的 WebDAV 服务接口
2. 将请求转发到另一个后端 WebDAV 服务
3. 支持基本的身份认证 (Basic Authentication)

## 功能特性

- 完整支持 WebDAV 协议
- 支持基本身份认证
- 可配置的代理规则
- 简单易用的配置

## 安装

```bash
# 安装依赖
pip install -r requirements.txt
```

## 配置

编辑 `.env` 文件（从 `.env.example` 复制）:

```
# 代理服务器配置
HOST=0.0.0.0
PORT=8080
AUTH_USERNAME=user
AUTH_PASSWORD=password

# 后端 WebDAV服务器配置
BACKEND_URL=https://example.com/webdav
BACKEND_USERNAME=backend_user
BACKEND_PASSWORD=backend_password

# 元数据缓存配置
METADATA_CACHE_SIZE=2000
METADATA_CACHE_TTL=60

# 日志配置
# 是否将日志写入文件，设置为true开启文件日志，false仅输出到控制台
ENABLE_FILE_LOGGING=false
# 日志级别：DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_LEVEL=INFO
# 日志文件路径（仅在ENABLE_FILE_LOGGING=true时生效）
LOG_FILE=webdav_proxy.log
```

## 运行

```bash
python main.py
```

## 使用

运行后，你可以使用任何 WebDAV 客户端连接到 `http://localhost:8080`，使用配置的用户名和密码进行身份验证。

## 依赖

- wsgidav: WebDAV 服务器实现
- python-dotenv: 环境变量管理
- requests: HTTP 客户端
