"""
WebDAV代理文件类
"""

import requests
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
        self.is_moved = False
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
        self.provider.clear_resource_meta(self.path)

    def delete(self):
        """删除文件"""
        if self.is_moved:
            return
        logger.info(f"删除文件: {self.path}")
        response = requests.request(
            method="DELETE",
            url=self.backend_url,
            auth=self.auth
        )
        err_list = []
        if response.status_code not in (200, 204):
            logger.error(f"删除文件 {self.path} 失败，状态码: {response.status_code}")
            err_list.append((self.path, response.status_code))
            return err_list

        logger.info(f"文件 {self.path} 删除成功")
        # 清理缓存的元数据，确保下次获取最新数据
        self.provider.clear_resource_meta(self.path)
        return err_list

    def copy_move_single(self, dest_path, *, is_move):
        """复制或移动文件"""
        dest_url = self.provider._get_backend_url(dest_path)
        method = "MOVE" if is_move else "COPY"
        action = "移动" if is_move else "复制"

        logger.info(f"{action}文件: {self.path} 到 {dest_path}")
        response = requests.request(
            method,
            url=self.backend_url,
            auth=self.auth,
            headers={"Destination": dest_url, "Overwrite": self.environ.get("HTTP_OVERWRITE")}
        )

        if response.status_code not in (201, 204):
            logger.error(f"{action}文件 {self.path} 到 {dest_path} 失败，状态码: {response.status_code}")
            raise DAVError(response.status_code)

        self.is_moved = is_move
        logger.info(f"文件 {self.path} {action}到 {dest_path} 成功")

    def resolve(self, script_name, path_info):
        return super().resolve(script_name, path_info)
