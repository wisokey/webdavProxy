"""
WebDAV代理文件类
"""

from wsgidav.dav_provider import DAVNonCollection

from .logger import logger
from .fileObjectProxy import FileObjectProxy

class WebDAVProxyNonCollection(DAVNonCollection):
    """文件代理实现，连接前端和后端服务器"""

    def __init__(self, path: str, environ: dict):
        super().__init__(path, environ)
        self.backend_url = self.provider._get_backend_url(path)
        self.auth = self.provider.auth
        self.meta = None
        self.upload_proxy = None

    def get_content_length(self):
        """获取文件大小"""
        if self.meta is None:
            self.meta = self.provider.get_resource_meta(self.path)
        return self.meta.get("content_length")

    def get_content_type(self):
        """获取文件类型"""
        if self.meta is None:
            self.meta = self.provider.get_resource_meta(self.path)
        content_type = self.meta.get("content_type")
        if content_type is None:
            # 如果后端返回的content_type为空，设置为application/octet-stream
            content_type = "application/octet-stream"
        return content_type

    def get_creation_date(self):
        """获取文件创建时间"""
        if self.meta is None:
            self.meta = self.provider.get_resource_meta(self.path)
        return self.meta.get("creation_date")

    def get_display_name(self):
        """获取文件显示名称"""
        if self.meta is None:
            self.meta = self.provider.get_resource_meta(self.path)
        return self.meta.get("display_name")

    def get_last_modified(self):
        """获取文件最后修改时间"""
        if self.meta is None:
            self.meta = self.provider.get_resource_meta(self.path)
        return self.meta.get("last_modified")

    def get_content(self):
        """获取文件内容 - 使用流式下载代理"""
        logger.info(f"获取文件内容: {self.path}")
        
        # 创建下载代理并返回，实现流式下载
        download_proxy = FileObjectProxy.create_download_proxy(
            self.path, 
            self.backend_url, 
            self.auth
        )
        
        return download_proxy

    def get_etag(self):
        """获取文件 ETag"""
        if self.meta is None:
            self.meta = self.provider.get_resource_meta(self.path)
        return self.meta.get("etag")

    def support_etag(self):
        # 支持 ETag
        return True

    def support_ranges(self):
        # 支持 Range
        return True

    def begin_write(self, *, content_type=None):
        """开始写入 - 创建并返回上传代理"""
        logger.info(f"开始上传文件: {self.path}")
        
        # 创建上传代理，实现流式上传
        self.upload_proxy = FileObjectProxy.create_upload_proxy(
            self.path, 
            self.backend_url, 
            self.auth, 
            content_type
        )
        
        return self.upload_proxy

    def end_write(self, *, with_errors):
        """完成写入 - 上传完成后的处理"""
        if with_errors:
            logger.error(f"文件上传出错: {self.path}")
            return
        
        # 获取上传状态
        if hasattr(self, 'upload_proxy') and self.upload_proxy:
            status = self.upload_proxy.get_status()
            if status.get('error'):
                logger.error(f"上传文件 {self.path} 失败: {status.get('error')}")
            else:
                logger.info(f"文件上传成功: {self.path}, 大小: {status.get('uploaded_bytes', 0)}字节")
        
        # 清空缓存的元数据，确保下次获取最新数据
        self.meta = None

    def resolve(self, script_name, path_info):
        return super().resolve(script_name, path_info)
