import os
from dotenv import load_dotenv

# 加载 .env 文件中的环境变量，强制重新加载
load_dotenv(override=True)

# 代理服务器配置
HOST = os.getenv('HOST', '0.0.0.0')
PORT = int(os.getenv('PORT', '8080'))
AUTH_USERNAME = os.getenv('AUTH_USERNAME', 'user')
AUTH_PASSWORD = os.getenv('AUTH_PASSWORD', 'password')

# WebDAV挂载路径配置 - 默认为/dav/
MOUNT_PATH = os.getenv('MOUNT_PATH', '/dav/')

# 后端 WebDAV 服务器配置
BACKEND_URL = os.getenv('BACKEND_URL', 'http://example.com/webdav')
BACKEND_USERNAME = os.getenv('BACKEND_USERNAME', 'backend_user')
BACKEND_PASSWORD = os.getenv('BACKEND_PASSWORD', 'backend_password')
