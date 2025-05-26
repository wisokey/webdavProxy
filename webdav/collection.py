"""
WebDAV代理集合（目录）类
"""

import os
import requests
from typing import Optional
from wsgidav.dav_provider import DAVCollection, _DAVResource
from wsgidav.util import join_uri
from wsgidav.dav_error import DAVError, HTTP_NOT_FOUND

from .logger import logger
from .utils import Utils

class WebDAVProxyCollection(DAVCollection):
    """WebDAV 代理集合（目录）"""
    
    def __init__(self, path: str, environ: dict):
        super().__init__(path, environ)
        self.backend_url = self.provider._get_backend_url(path)
        self.auth = self.provider.auth
        self.meta = None

    def create_empty_resource(self, name: str) -> _DAVResource:
        """创建空资源（文件）"""
        path = join_uri(self.path, name)
        backend_url = self.provider._get_backend_url(path)

        logger.info(f"创建空文件: {path}")
        response = requests.request(
            method="PUT",
            url=backend_url,
            auth=self.auth,
            data=b""
        )

        if response.status_code not in (201, 204):
            logger.error(f"创建空文件 {path} 失败，状态码: {response.status_code}")
            raise DAVError(response.status_code)

        logger.info(f"空文件 {path} 创建成功")
        return True

    def create_collection(self, name):
        """创建集合（目录）"""
        path = join_uri(self.path, name)
        backend_url = self.provider._get_backend_url(path)

        logger.info(f"创建目录: {path}")
        response = requests.request(
            method="MKCOL",
            url=backend_url,
            auth=self.auth
        )

        if response.status_code not in (201, 204):
            logger.error(f"创建目录 {path} 失败，状态码: {response.status_code}")
            raise DAVError(response.status_code)

        logger.info(f"目录 {path} 创建成功")
        return True

    def get_member_names(self):
        """获取集合成员名称列表"""
        logger.info(f"获取目录 {self.path} 成员名称列表")

        result = Utils.propfind(self.backend_url, self.auth)
        self.provider.set_resource_meta(result)
        if result is None:
            raise DAVError(HTTP_NOT_FOUND)

        member_names = []
        for href, meta in result.items():
            # 去除 href 中携带的后端 URL 前缀
            if (href.startswith(self.provider.backend_url)):
                href = href.replace(self.provider.backend_url, '', 1)
            elif (self.provider.backend_path != '/' and href.startswith(self.provider.backend_path)):
                href = href.replace(self.provider.backend_path, '', 1)
            # 校验 href 是否是自身
            if href == self.path:
                continue
            name = href.replace(self.path, '', 1)
            member_names.append(name)
        logger.info(f"目录 {self.path} 列表: {', '.join(member_names)}"[:1000])
        return member_names

    def delete(self):
        """删除集合（目录）"""
        logger.info(f"删除目录: {self.path}")

        response = requests.request(
            method="DELETE",
            url=self.backend_url,
            auth=self.auth
        )

        if response.status_code not in (200, 204):
            logger.error(f"删除目录 {self.path} 失败，状态码: {response.status_code}")
            raise DAVError(response.status_code)

        logger.info(f"目录 {self.path} 删除成功")
        return True

    def copy_move_single(self, dest_path, *, is_move):
        """复制或移动集合（目录）"""
        dest_url = self.provider._get_backend_url(dest_path)
        method = "MOVE" if is_move else "COPY"
        action = "移动" if is_move else "复制"

        logger.info(f"{action}目录: {self.path} 到 {dest_path}")
        response = requests.request(
            method,
            url=self.backend_url,
            auth=self.auth,
            headers={"Destination": dest_url, "Overwrite": "T"}
        )

        if response.status_code not in (201, 204):
            logger.error(f"{action}目录 {self.path} 到 {dest_path} 失败，状态码: {response.status_code}")
            raise DAVError(response.status_code)

        logger.info(f"目录 {self.path} {action}到 {dest_path} 成功")
        return True

    def support_recursive_delete(self):
        # 支持递归删除
        return True

    def support_recursive_move(self, dest_path):
        # 支持递归移动
        return True

    def move_recursive(self, dest_path):
        """递归移动集合（目录）"""
        logger.info(f"递归移动目录: {self.path} 到 {dest_path}")
        dest_url = self.provider._get_backend_url(dest_path)
        response = requests.request(
            method="MOVE",
            url=self.backend_url,
            auth=self.auth,
            headers={"Destination": dest_url, "Overwrite": "T"}
        )

        if response.status_code not in (201, 204):
            logger.error(f"递归移动目录 {self.path} 到 {dest_path} 失败，状态码: {response.status_code}")
            raise DAVError(response.status_code)

        logger.info(f"目录 {self.path} 递归移动到 {dest_path} 成功")
        return True

    def get_creation_date(self):
        if self.meta is None:
            self.meta = self.provider.get_resource_meta(self.path)
        return self.meta.get("creation_date")

    def get_display_name(self):
        if self.meta is None:
            self.meta = self.provider.get_resource_meta(self.path)
        return self.meta.get("display_name")

    def get_last_modified(self):
        if self.meta is None:
            self.meta = self.provider.get_resource_meta(self.path)
        return self.meta.get("last_modified")

    def get_content_length(self) -> Optional[int]:
        return super().get_content_length()

    def get_content_type(self) -> Optional[str]:
        return super().get_content_type()

    def get_etag(self):
        return super().get_etag()

    def get_member(self, name):
        return super().get_member(name)

    def support_etag(self):
        return super().support_etag()

    def resolve(self, script_name, path_info):
        return super().resolve(script_name, path_info)