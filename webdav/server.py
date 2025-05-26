"""
WebDAV服务器配置和初始化
"""

from wsgidav.wsgidav_app import WsgiDAVApp
from wsgidav.util import init_logging
from waitress import serve

from .provider import WebDAVProxy
from .logger import logger

class WebDAVServer:
    """WebDAV服务器配置和管理类"""
    
    def __init__(self, backend_url, backend_username, backend_password, 
                 auth_username, auth_password, host="0.0.0.0", port=8080):
        """初始化WebDAV服务器"""
        self.backend_url = backend_url
        self.backend_username = backend_username
        self.backend_password = backend_password
        self.auth_username = auth_username
        self.auth_password = auth_password
        self.host = host
        self.port = port
        
    def create_app(self):
        """创建WsgiDAV应用程序"""
        # 配置日志
        init_logging({"verbose": 3})
        
        # 配置WebDAV提供程序
        provider = WebDAVProxy(
            backend_url=self.backend_url,
            backend_username=self.backend_username,
            backend_password=self.backend_password
        )
        
        # 配置WsgiDAV应用程序
        app_config = {
            "provider_mapping": {"/": provider},
            "http_authenticator": {
                # 使用简单的身份验证方式
                "accept_basic": True,
                "accept_digest": False,
                "default_to_digest": False,
            },
            # 直接在配置中指定用户凭据
            "simple_dc": {
                "user_mapping": {
                    "/": {self.auth_username: {"password": self.auth_password}}
                },
            },
            "verbose": 1,
            "logging": {
                "enable_loggers": []
            },
            "property_manager": True,
            "lock_storage": False,  # 禁用锁功能，不处理LOCK和UNLOCK请求
        }
        
        return WsgiDAVApp(app_config)
        
    def start(self):
        """启动WebDAV服务器"""
        app = self.create_app()
        
        logger.info(f"WebDAV代理服务器启动于http://{self.host}:{self.port}")
        logger.info(f"转发到后端WebDAV服务器: {self.backend_url}")
        
        # 使用waitress作为WSGI服务器
        serve(app, host=self.host, port=self.port)
