"""FileObjectProxy 类 - 用于WebDAV代理的流式文件传输

此类用于WebDAV代理与后端WebDAV服务器之间的流式传输，
支持以下功能：
1. 从后端WebDAV流式下载文件传给客户端
2. 支持流式上传操作至后端WebDAV服务器
3. 实现类文件对象接口，与wsgidav框架兼容
"""

import io
import requests
import queue
import threading
from typing import Optional, Tuple, Dict, Any, Union

from .logger import logger


class FileObjectDownloadProxy(io.RawIOBase):
    """文件下载代理 - 用于从后端WebDAV流式下载文件"""

    def __init__(self, path: str, backend_url: str, auth: Tuple[str, str], 
                 headers: Optional[Dict[str, str]] = None):
        super(FileObjectDownloadProxy, self).__init__()
        self.path = path
        self.backend_url = backend_url
        self.auth = auth
        self.headers = headers or {}
        self.position = 0
        self.response = None
        self.stream = None
        self.content_length = self._get_content_length()
        logger.debug(f"初始化文件下载代理: {path}, 大小: {self.content_length}字节")

    def _get_content_length(self) -> int:
        """获取文件大小"""
        try:
            response = requests.head(self.backend_url, auth=self.auth, headers=self.headers)
            if response.status_code == 200 and 'Content-Length' in response.headers:
                return int(response.headers['Content-Length'])
            else:
                logger.warning(f"无法获取文件大小, 状态码: {response.status_code}")
                return 0
        except Exception as e:
            logger.error(f"获取文件大小失败: {e}")
            return 0

    def _ensure_stream(self) -> None:
        """确保流已打开"""
        if self.stream is None:
            try:
                headers = self.headers.copy()
                # 如果位置不是0，使用Range请求从当前位置开始
                if self.position > 0:
                    headers['Range'] = f'bytes={self.position}-'
                
                self.response = requests.get(
                    self.backend_url, 
                    auth=self.auth, 
                    stream=True, 
                    headers=headers
                )
                
                if self.response.status_code not in (200, 206):
                    raise IOError(f"HTTP错误: {self.response.status_code}")
                    
                self.stream = self.response.iter_content(chunk_size=8192)
                logger.debug(f"打开文件下载流: {self.path}, 位置: {self.position}")
            except Exception as e:
                logger.error(f"打开文件下载流失败: {e}")
                raise

    def readable(self) -> bool:
        return True

    def writable(self) -> bool:
        return False

    def seekable(self) -> bool:
        return True

    def read(self, size: int = -1) -> bytes:
        """读取指定大小的数据"""
        if self.closed:
            raise ValueError("I/O operation on closed file")

        self._ensure_stream()

        try:
            if size == -1 or size is None:
                # 读取所有剩余内容
                data = b''.join(self.stream)
                bytes_read = len(data)
            else:
                # 读取指定大小的内容
                data = b''
                bytes_remaining = size

                while bytes_remaining > 0:
                    try:
                        chunk = next(self.stream)
                        if not chunk:
                            break

                        if len(chunk) <= bytes_remaining:
                            data += chunk
                            bytes_remaining -= len(chunk)
                        else:
                            # 如果分块大于所需大小，只取需要的部分
                            data += chunk[:bytes_remaining]
                            # 这里不处理剩余部分，因为大多数WebDAV客户端会顺序读取
                            bytes_remaining = 0
                    except StopIteration:
                        break

                bytes_read = size - bytes_remaining

            self.position += bytes_read
            logger.debug(f"读取文件数据: {self.path}, 大小: {bytes_read}字节, 新位置: {self.position}")
            return data

        except Exception as e:
            logger.error(f"读取文件数据失败: {e}")
            return b''

    def seek(self, offset: int, whence: int = io.SEEK_SET) -> int:
        """移动文件指针位置"""
        if self.closed:
            raise ValueError("I/O operation on closed file")

        if whence == io.SEEK_SET:
            new_position = offset
        elif whence == io.SEEK_CUR:
            new_position = self.position + offset
        elif whence == io.SEEK_END:
            new_position = self.content_length + offset
        else:
            raise ValueError(f"无效的whence值: {whence}")

        if new_position < 0:
            new_position = 0

        # 如果位置发生变化，重置流
        if new_position != self.position:
            self.position = new_position
            if self.stream is not None:
                self.stream = None
                if self.response is not None:
                    self.response.close()
                    self.response = None

        return self.position

    def tell(self) -> int:
        """返回当前文件指针位置"""
        if self.closed:
            raise ValueError("I/O operation on closed file")
        return self.position

    def close(self) -> None:
        """关闭文件对象"""
        if not self.closed:
            if self.response is not None:
                self.response.close()
                self.response = None
                self.stream = None
            logger.debug(f"关闭文件下载代理: {self.path}")
        super(FileObjectDownloadProxy, self).close()


class FileObjectUploadProxy(io.RawIOBase):
    """文件上传代理 - 用于向后端WebDAV流式上传文件
    
    使用一个线程和一个HTTP请求完成整个文件的上传，真正的流式上传
    """

    # 定义上传状态
    STATUS_INIT = 0      # 初始化状态
    STATUS_UPLOADING = 1 # 正在上传中
    STATUS_DONE = 2      # 上传完成
    STATUS_ERROR = 3     # 上传错误

    def __init__(self, path: str, backend_url: str, auth: Tuple[str, str], 
                 content_type: Optional[str] = None):
        super(FileObjectUploadProxy, self).__init__()
        self.path = path
        self.backend_url = backend_url
        self.auth = auth
        self.content_type = content_type

        # 上传相关状态
        self.upload_status = self.STATUS_INIT
        self.uploaded_bytes = 0
        self.error_message = None

        # 初始化线程和队列
        self._queue = queue.Queue()
        self._upload_thread = threading.Thread(target=self._upload_worker)
        self._upload_started = False

        # 请求相关
        self.headers = {}
        if self.content_type:
            self.headers['Content-Type'] = self.content_type

        logger.debug(f"初始化文件上传代理: {path}, 内容类型: {content_type}")
        
        # 启动上传线程
        self._start_upload()

    def _start_upload(self):
        """启动上传线程"""
        if not self._upload_started:
            self._upload_started = True
            self._upload_thread.daemon = True  # 设置为后台线程
            self._upload_thread.start()
            self.upload_status = self.STATUS_UPLOADING
            logger.debug(f"启动上传线程: {self.path}")

    def _data_generator(self):
        """生成数据生成器，从队列中获取数据块"""
        while self._upload_started:
            try:
                chunk = self._queue.get()
                if chunk is None:  # None作为结束标志
                    break
                self.uploaded_bytes += len(chunk)
                yield chunk
                self._queue.task_done()
            except Exception as e:
                logger.error(f"从队列获取数据错误: {e}")
                break

    def _upload_worker(self):
        """上传线程函数"""
        try:
            logger.info(f"开始流式上传文件: {self.path}")
            response = requests.put(
                self.backend_url,
                auth=self.auth,
                data=self._data_generator(),  # 使用生成器提供数据
                headers=self.headers
            )

            if response.status_code in (200, 201, 204, 206):
                self.upload_status = self.STATUS_DONE
                logger.info(f"文件上传成功: {self.path}, 总大小: {self.uploaded_bytes}字节")
            else:
                self.error_message = f"上传失败，状态码: {response.status_code}"
                self.upload_status = self.STATUS_ERROR
                logger.error(f"上传文件 {self.path} 失败，状态码: {response.status_code}")

        except Exception as e:
            self.error_message = str(e)
            self.upload_status = self.STATUS_ERROR
            logger.error(f"上传文件 {self.path} 失败: {e}")

    def readable(self) -> bool:
        return False

    def writable(self) -> bool:
        return True

    def write(self, data: bytes) -> int:
        """将数据写入队列，供上传线程使用"""
        if self.closed:
            raise ValueError("I/O operation on closed file")

        if self.upload_status == self.STATUS_ERROR:
            raise IOError(f"上传错误: {self.error_message}")

        data_size = len(data)
        self._queue.put(data)
        logger.debug(f"写入数据块到上传队列: {self.path}, 大小: {data_size}字节")
        return data_size

    def close(self) -> None:
        """关闭文件对象并上传所有剩余数据"""
        if not self.closed:
            try:
                # 确保队列中的数据全部上传
                if self._queue.qsize() > 0 and self.upload_status != self.STATUS_ERROR:
                    self._queue.put(None)  # None作为结束标志
                    self._upload_thread.join()  # 等待上传线程结束
            except Exception as e:
                self.error_message = str(e)
                self.upload_status = self.STATUS_ERROR
                logger.error(f"关闭时上传文件 {self.path} 失败: {e}")
            finally:
                super(FileObjectUploadProxy, self).close()
                logger.debug(f"关闭文件上传代理: {self.path}, 已上传数据: {self.uploaded_bytes}字节")


    def get_status(self) -> Dict[str, Any]:
        """获取上传状态"""
        return {
            'path': self.path,
            'uploaded_bytes': self.uploaded_bytes,
            'status': self.upload_status,
            'closed': self.closed,
            'error': self.error_message
        }


class FileObjectProxy:
    """文件对象代理工厂类 - 根据需要创建下载或上传代理"""

    @staticmethod
    def create_download_proxy(path: str, backend_url: str, auth: Tuple[str, str], 
                             headers: Optional[Dict[str, str]] = None) -> FileObjectDownloadProxy:
        """创建下载代理"""
        return FileObjectDownloadProxy(path, backend_url, auth, headers)

    @staticmethod
    def create_upload_proxy(path: str, backend_url: str, auth: Tuple[str, str], 
                           content_type: Optional[str] = None) -> FileObjectUploadProxy:
        """创建上传代理"""
        return FileObjectUploadProxy(path, backend_url, auth, content_type)
