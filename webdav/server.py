"""
WebDAV服务器配置和初始化
"""

from wsgidav.wsgidav_app import WsgiDAVApp
from wsgidav.util import init_logging
from cheroot import wsgi
from urllib.parse import quote

from .provider import WebDAVProxy
from .logger import logger

class WebDAVServer:
    """WebDAV服务器配置和管理类"""

    def __init__(self, backend_url, backend_username, backend_password, 
                 auth_username, auth_password, host="0.0.0.0", port=8080, mount_path="/"):
        """初始化WebDAV服务器"""
        self.backend_url = backend_url
        self.backend_username = backend_username
        self.backend_password = backend_password
        self.auth_username = auth_username
        self.auth_password = auth_password
        self.host = host
        self.port = port
        self.mount_path = mount_path.rstrip("/") + "/" if not mount_path.endswith("/") else mount_path  # 确保路径以/结尾

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
            "provider_mapping": {self.mount_path: provider},
            "http_authenticator": {
                # 使用简单的身份验证方式
                "accept_basic": True,
                "accept_digest": False,
                "default_to_digest": False,
            },
            # 直接在配置中指定用户凭据
            "simple_dc": {
                "user_mapping": {
                    "*": {self.auth_username: {"password": self.auth_password}}
                },
            },
            "verbose": 1,
            "logging": {
                "enable_loggers": []
            },
            "property_manager": True,
            "lock_storage": False,  # 禁用锁功能，不处理LOCK和UNLOCK请求
        }

        # 创建WsgiDAV应用
        app = WsgiDAVApp(app_config)

        # 如果挂载路径不是根目录，则添加中间件将根目录请求重定向到挂载路径
        if self.mount_path != "/":
            return self._create_root_redirect_middleware(app)
        return app

    def _create_root_redirect_middleware(self, app):
        """创建一个中间件，将根目录的请求重定向到挂载路径"""
        mount_path = self.mount_path

        def root_redirect_middleware(environ, start_response):
            path_info = environ.get('PATH_INFO', '')

            # 如果是根路径请求，重定向到挂载路径
            if path_info == '/' or path_info == '':
                # 构造重定向URL
                redirect_url = mount_path
                if not redirect_url.endswith('/'):
                    redirect_url += '/'

                # 设置重定向响应头
                headers = [('Location', quote(redirect_url)), 
                           ('Content-Type', 'text/html')]
                start_response('302 Found', headers)
                return [f'<html><body>重定向到 <a href="{redirect_url}">{redirect_url}</a></body></html>'.encode('utf-8')]

            # 其他请求正常处理
            return app(environ, start_response)

        return root_redirect_middleware

    def start(self):
        """启动WebDAV服务器"""
        app = self.create_app()

        logger.info(f"WebDAV代理服务器启动于http://{self.host}:{self.port}{self.mount_path}")
        logger.info(f"转发到后端WebDAV服务器: {self.backend_url}")

        # 使用Cheroot作为WSGI服务器
        server = wsgi.Server((self.host, self.port), app)
        try:
            server.start()
        except KeyboardInterrupt:
            server.stop()
