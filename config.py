import yaml
from pathlib import Path

# 配置文件路径
CONFIG_FILE = Path(__file__).parent / 'config.yaml'

# 加载配置文件
config_data = {}
try:
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        config_data = yaml.safe_load(f)
except (FileNotFoundError, yaml.YAMLError) as e:
    print(f"无法加载配置文件: {e}，使用默认配置")

HOST = config_data.get('HOST', '0.0.0.0')
PORT = config_data.get('PORT', 8080)
MOUNT_PATH = config_data.get('MOUNT_PATH', '/dav/')
AUTH_USERNAME = config_data.get('AUTH_USERNAME', 'user')
AUTH_PASSWORD = config_data.get('AUTH_PASSWORD', 'password')
BACKEND_URL = config_data.get('BACKEND_URL', 'http://example.com/webdav')
BACKEND_USERNAME = config_data.get('BACKEND_USERNAME', 'backend_user')
BACKEND_PASSWORD = config_data.get('BACKEND_PASSWORD', 'backend_password')
METADATA_CACHE_SIZE = config_data.get('METADATA_CACHE_SIZE', 2000)
METADATA_CACHE_TTL = config_data.get('METADATA_CACHE_TTL', 60)
ENABLE_FILE_LOGGING = config_data.get('ENABLE_FILE_LOGGING', False)
LOG_LEVEL = config_data.get('LOG_LEVEL', 'INFO')
LOG_FILE = config_data.get('LOG_FILE', 'webdav_proxy.log')
