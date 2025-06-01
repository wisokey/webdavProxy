"""
提供一些工具函数
"""

import os
import json
import asyncio
import requests
import aiohttp
import email.utils
import urllib.parse
from datetime import datetime
from lxml import etree
from aiohttp.helpers import BasicAuth

from .logger import logger

class Utils:
    """ 工具类 """

    # 调用 PROPFIND 方法 获取后端资源列表
    @staticmethod
    def propfind(folder_path, auth):
        result = {}
        try:
            response = requests.request(
                method="PROPFIND",
                url=folder_path,
                auth=auth,
                headers={"Depth": "1"},
                timeout=10
            )
            if response.status_code != 207:
                logger.warning(f"获取资源元数据失败，路径: {folder_path}, 状态码: {response.status_code}")
                return None
            multistatus = etree.fromstring(response.content)
            ns = {'D': 'DAV:'}
            for item in multistatus:
                prop = item.xpath('./D:propstat/D:prop', namespaces=ns)[0]
                href = item.xpath('./D:href', namespaces=ns)[0].text
                decoded_href = urllib.parse.unquote(href, encoding='utf-8', errors='strict')

                meta = {}
                for attr in prop:
                    if attr.tag.endswith('resourcetype'):
                        meta['is_collection'] = len(attr.xpath('./D:collection', namespaces=ns)) > 0
                    elif attr.tag.endswith('getcontentlength'):
                        meta['content_length'] = int(attr.text)
                    elif attr.tag.endswith('getcontenttype'):
                        meta['content_type'] = attr.text
                    elif attr.tag.endswith('displayname'):
                        meta['display_name'] = attr.text
                    elif attr.tag.endswith('getetag'):
                        meta['etag'] = attr.text.replace('"', '')
                    elif attr.tag.endswith('creationdate'):
                        # 将ISO 8601转换为时间戳
                        meta['creation_date'] = datetime.fromisoformat(attr.text).timestamp()
                    elif attr.tag.endswith('getlastmodified'):
                        # 将RFC 822转换为时间戳
                        meta['last_modified'] = email.utils.parsedate_to_datetime(attr.text).timestamp()
                # 检查 is_collection 是否存在
                if 'is_collection' not in meta:
                    raise Exception(f"获取资源元数据失败，路径: {folder_path}, 缺少 is_collection")
                result[decoded_href] = meta

            # 开始处理分割文件
            split_file_list = []
            need_remove_list = []
            # 检查是否存在分割文件
            for key, value in result.items():
                if key.endswith('.splitinfo'):
                    need_remove_list.append(key)
                    name = key[:-len('.splitinfo')]
                    # 校验分割文件是否完整，（目前先简易判断第一个文件是否存在）
                    if name in result:
                        split_file_list.append(name)
                if key.split('.')[-1].startswith('part'):
                    need_remove_list.append(key)
            # 处理分割文件
            tasks = []
            auth_obj = BasicAuth(login=auth[0], password=auth[1])
            for key in split_file_list:
                meta = result[key]
                url = folder_path + '/' + os.path.basename(key) + '.splitinfo'
                tasks.append(Utils.get_split_info(url, auth_obj, meta))

            # 在线程中创建新的事件循环并运行异步任务
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                if tasks:
                    loop.run_until_complete(asyncio.gather(*tasks))
            finally:
                loop.close()
                asyncio.set_event_loop(None)

            # 移除分割文件
            for key in need_remove_list:
                result.pop(key)
            return result

        except Exception as e:
            logger.error(f"获取资源元数据时发生异常: {folder_path}, 错误: {str(e)}")
            return None

    @staticmethod
    async def get_split_info(path, auth, meta):
        try:
            # 使用aiohttp 从 后端获取分割文件信息
            async with aiohttp.ClientSession() as session:
                async with session.get(path, auth=auth) as response:
                    if response.status != 200:
                        raise Exception(f"获取分割文件信息失败，状态码: {response.status}")
                    split_info = await response.text()
                    split_info = json.loads(split_info)
                    meta['content_length'] = split_info['meta']['content_length']
                    meta['split_info'] = split_info
                    return meta
        except Exception as e:
            logger.error(f"获取分割文件信息时发生异常: {path}, 错误: {str(e)}")
            return None

    @staticmethod
    def encode_url(url):
        parts = urllib.parse.urlparse(url)

        # 只编码路径和查询部分
        encoded_path = urllib.parse.quote(parts.path, safe='/')
        encoded_query = urllib.parse.quote(parts.query, safe='=&')

        # 重新组合URL
        return urllib.parse.urlunsplit((parts.scheme, parts.netloc, encoded_path, encoded_query, parts.fragment))