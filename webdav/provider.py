"""
WebDAV代理提供者
"""

import os
import urllib.parse
from cachetools import TTLCache
from wsgidav.dav_provider import DAVProvider

import config
from .utils import Utils
from .logger import logger
from .collection import WebDAVProxyCollection
from .nonCollection import WebDAVProxyNonCollection

class WebDAVProxy(DAVProvider):
    """WebDAV 代理提供者，将请求转发到后端 WebDAV 服务"""

    def __init__(self, backend_url, backend_username, backend_password):
        super().__init__()
        self.backend_url = backend_url.rstrip("/")
        self.backend_username = backend_username
        self.backend_password = backend_password
        self.auth = (backend_username, backend_password) if backend_username and backend_password else None
        # 添加资源元数据缓存 - 从环境变量获取配置
        cache_size = config.METADATA_CACHE_SIZE
        cache_ttl = config.METADATA_CACHE_TTL
        self.resource_meta_cache = TTLCache(maxsize=cache_size, ttl=cache_ttl)
        logger.info(f"元数据缓存配置: 大小={cache_size}, TTL={cache_ttl}秒")
        # 拆解后端url,获取路径部分
        self.backend_path = urllib.parse.urlparse(self.backend_url).path
        logger.info(f"WebDAV代理初始化，后端URL: {self.backend_url}")

    def _get_backend_url(self, path):
        """构建后端 URL"""
        path = path.strip("/")
        return f"{self.backend_url}/{path}"

    def get_resource_inst(self, path, environ):
        meta = self.get_resource_meta(path)
        if meta is None:
            return None
        elif meta.get('is_collection'):
            return WebDAVProxyCollection(path, environ)
        else:
            return WebDAVProxyNonCollection(path, environ)

    def get_resource_meta(self, path, refresh=False):
        """获取资源元数据，包括 content_length,content_type,
        creation_date,display_name,etag,last_modified,is_collection

        Args:
            path: 资源路径
            refresh: 是否强制刷新缓存

        Returns:
            包含元数据的字典
        """
        # 检查缓存
        if not refresh and path in self.resource_meta_cache:
            return self.resource_meta_cache[path]

        # 发送PROPFIND请求从后端获取元数据
        backend_url = self._get_backend_url(path)
        # 为避免请求次数过多，每次以文件夹为单位请求
        folder_path = os.path.dirname(backend_url)

        result = Utils.propfind(folder_path, self.auth)
        if result is None:
            return None

        for key, value in result.items():
            # 去除 key 中开头的 self.backend_url
            if (key.startswith(self.backend_url)):
                key = key.replace(self.backend_url, '', 1)
            elif (self.backend_path != '/' and key.startswith(self.backend_path)):
                key = key.replace(self.backend_path, '', 1)
            self.resource_meta_cache[key] = value

        return self.resource_meta_cache.get(path)

    def set_resource_meta(self, cacheData):
        """设置资源元数据缓存"""
        if cacheData is None:
            return
        for key, value in cacheData.items():
            # 去除 key 中开头的 self.backend_url
            if (key.startswith(self.backend_url)):
                key = key.replace(self.backend_url, '', 1)
            elif (self.backend_path != '/' and key.startswith(self.backend_path)):
                key = key.replace(self.backend_path, '', 1)
            self.resource_meta_cache[key] = value

    def clear_resource_meta(self, path):
        """清理资源元数据缓存"""
        if not path.endswith('/') and path in self.resource_meta_cache:
            self.resource_meta_cache.pop(path)
            return
        keys = self.resource_meta_cache.keys()
        for key in keys:
            if key.startswith(path):
                self.resource_meta_cache.pop(key)
        return

    def is_readonly(self):
        return super().is_readonly()

    def set_mount_path(self, mount_path):
        super().set_mount_path(mount_path)

    def set_share_path(self, share_path):
        super().set_share_path(share_path)

    def set_lock_manager(self, lock_manager):
        super().set_lock_manager(lock_manager)

    def set_prop_manager(self, prop_manager):
        super().set_prop_manager(prop_manager)

    def ref_url_to_path(self, ref_url):
        return super().ref_url_to_path(ref_url)

    def exists(self, path: str, environ: dict):
        return super().exists(path, environ)

    def is_collection(self, path: str, environ: dict):
        return super().is_collection(path, environ)

    def custom_request_handler(self, environ, start_response, default_handler):
        return super().custom_request_handler(environ, start_response, default_handler)
