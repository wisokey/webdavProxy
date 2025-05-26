"""
提供一些工具函数
"""

import requests
import email.utils
import urllib.parse
from datetime import datetime
from lxml import etree


from .logger import logger

class Utils:
    """ 工具类 """
    
    # 调用 PROPFIND 方法 获取后端资源列表
    @staticmethod
    def propfind(path, auth):
        result = {}
        try:
            response = requests.request(
                method="PROPFIND",
                url=path,
                auth=auth,
                headers={"Depth": "1"},
                timeout=10
            )
            if response.status_code != 207:
                logger.warning(f"获取资源元数据失败，路径: {path}, 状态码: {response.status_code}")
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
                    raise Exception(f"获取资源元数据失败，路径: {path}, 缺少 is_collection")
                result[decoded_href] = meta
            return result

        except Exception as e:
            logger.error(f"获取资源元数据时发生异常: {path}, 错误: {str(e)}")
            return None