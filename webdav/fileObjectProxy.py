"""FileObjectProxy 类 - 用于WebDAV代理的流式文件传输

此类用于WebDAV代理与后端WebDAV服务器之间的流式传输，
支持以下功能：
1. 从后端WebDAV流式下载文件传给客户端
2. 支持流式上传操作至后端WebDAV服务器
3. 实现类文件对象接口，与wsgidav框架兼容
"""

import io
import requests
import json
import queue
import threading
from typing import Optional, Tuple, Dict, Any

from config import FILE_MAX_SIZE
from .logger import logger

class FileObjectDownloadProxy(io.RawIOBase):
    """文件下载代理 - 用于从后端WebDAV流式下载文件（支持分片文件）"""

    def __init__(self, path: str, backend_url: str, auth: Tuple[str, str], 
                 headers: Optional[Dict[str, str]] = None, meta: Optional[Dict[str, Any]] = None):
        super(FileObjectDownloadProxy, self).__init__()
        self.path = path
        self.backend_url = backend_url
        self.auth = auth
        self.headers = headers or {}
        self.position = 0
        self.response = None
        self.stream = None
        self.file_split_info = meta.get('split_info') if meta else None
        self.content_length = meta.get('content_length', 0) if meta else 0
        self._buffer = b''  # 用于缓存读取的数据块
        
        # 处理分片文件信息
        self._parts = []
        self._current_part_index = -1
        self._current_part_stream = None
        self._current_part_response = None
        self._current_part_position = 0
        
        if self.file_split_info:
            split_list = self.file_split_info.get('splitFileList', [])
            current_start = 0
            for part in split_list:
                part_size = int(part.get('fileSize', 0))
                self._parts.append({
                    'url': self._get_part_url(part.get('fileName', '')),
                    'size': part_size,
                    'start': current_start,
                    'end': current_start + part_size
                })
                current_start += part_size
            logger.debug(f"分片文件: {path}, 分片数: {len(self._parts)}, 总大小: {self.content_length}字节")
        else:
            logger.debug(f"初始化文件下载代理: {path}, 大小: {self.content_length}字节")

    def _get_part_url(self, filename: str) -> str:
        """构建分片文件的完整URL"""
        return self.backend_url.rsplit('/', 1)[0] + '/' + filename

    def _ensure_stream(self) -> None:
        """确保流已打开（主文件或当前分片）"""
        if self.file_split_info:
            # 分片文件逻辑
            if self._current_part_index < 0 or self._current_part_stream is None:
                self._locate_current_part()
                self._open_current_part()
        else:
            # 原始单文件逻辑
            if self.stream is None:
                try:
                    headers = self.headers.copy()
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

    def _locate_current_part(self) -> None:
        """根据当前位置定位到对应的分片"""
        if self.position >= self.content_length:
            # 超出文件范围，定位到最后一个分片末尾
            self._current_part_index = len(self._parts) - 1
            self._current_part_position = self._parts[-1]['size']
            return
        
        # 查找当前分片
        for idx, part in enumerate(self._parts):
            if part['start'] <= self.position < part['end']:
                self._current_part_index = idx
                self._current_part_position = self.position - part['start']
                return
        
        # 默认定位到第一个分片
        self._current_part_index = 0
        self._current_part_position = 0

    def _open_current_part(self) -> None:
        """打开当前分片文件的流"""
        if self._current_part_index < 0 or self._current_part_index >= len(self._parts):
            return
            
        # 关闭之前的分片流
        if self._current_part_response:
            self._current_part_response.close()
            
        part = self._parts[self._current_part_index]
        try:
            headers = self.headers.copy()
            if self._current_part_position > 0:
                headers['Range'] = f'bytes={self._current_part_position}-'
            
            self._current_part_response = requests.get(
                part['url'],
                auth=self.auth,
                stream=True,
                headers=headers
            )
            
            if self._current_part_response.status_code not in (200, 206):
                raise IOError(f"分片HTTP错误: {self._current_part_response.status_code}")
            
            self._current_part_stream = self._current_part_response.iter_content(chunk_size=8192)
            logger.debug(f"打开分片 #{self._current_part_index}: {part['url']}, 位置: {self._current_part_position}")
        except Exception as e:
            logger.error(f"打开分片文件失败: {e}")
            raise

    def _switch_to_next_part(self) -> bool:
        """切换到下一个分片"""
        if self._current_part_index < 0 or self._current_part_index >= len(self._parts) - 1:
            return False  # 没有后续分片
            
        # 关闭当前分片
        if self._current_part_response:
            self._current_part_response.close()
        
        # 定位到下一个分片
        self._current_part_index += 1
        self._current_part_position = 0
        self._open_current_part()
        return True

    def readable(self) -> bool:
        return True

    def writable(self) -> bool:
        return False

    def seekable(self) -> bool:
        return True

    def read(self, size: int = -1) -> bytes:
        if self.closed:
            raise ValueError("I/O operation on closed file")
            
        # 处理分片文件读取
        if self.file_split_info:
            if size == 0:
                return b''
                
            self._ensure_stream()
            data = b''
            remaining = size if size > 0 else float('inf')
            
            while remaining > 0:
                # 优先使用缓冲区数据
                if self._buffer:
                    chunk = self._buffer[:min(remaining, len(self._buffer))]
                    self._buffer = self._buffer[len(chunk):]
                    data += chunk
                    self.position += len(chunk)
                    remaining -= len(chunk)
                    if remaining <= 0:
                        break
                
                # 从当前分片读取
                if self._current_part_stream is not None:
                    try:
                        chunk = next(self._current_part_stream)
                        # 处理读取量超过需求的情况
                        if len(chunk) > remaining:
                            data += chunk[:remaining]
                            self._buffer = chunk[remaining:]  # 缓存多余数据
                            self.position += remaining
                            remaining = 0
                        else:
                            data += chunk
                            self.position += len(chunk)
                            remaining -= len(chunk)
                    except StopIteration:
                        # 当前分片结束，尝试切换分片
                        if not self._switch_to_next_part():
                            break
                else:
                    break
                    
            logger.debug(f"读取分片文件: {self.path}, 大小: {len(data)}字节, 位置: {self.position}")
            return data
            
        else:
            # 原始单文件读取逻辑
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
                                # 缓存多余数据
                                self._buffer = chunk[bytes_remaining:]
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
            
        new_position = 0
        if whence == io.SEEK_SET:
            new_position = offset
        elif whence == io.SEEK_CUR:
            new_position = self.position + offset
        elif whence == io.SEEK_END:
            new_position = self.content_length + offset
        else:
            raise ValueError(f"无效的whence值: {whence}")

        new_position = max(0, min(new_position, self.content_length))
        
        # 清空缓冲区（位置变化时）
        if new_position != self.position:
            self._buffer = b''
        
        # 更新位置并重置流
        if new_position != self.position:
            self.position = new_position
            if self.file_split_info:
                # 分片文件：重置分片流
                if self._current_part_response is not None:
                    self._current_part_response.close()
                    self._current_part_response = None
                    self._current_part_stream = None
                self._current_part_index = -1
            else:
                # 单文件：重置流
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
        if not self.closed:
            # 关闭所有可能的资源
            if self.file_split_info:
                if self._current_part_response is not None:
                    self._current_part_response.close()
                    self._current_part_response = None
                    self._current_part_stream = None
            else:
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
        self.total_uploaded_bytes = 0
        self.error_message = None

        # 初始化线程和队列
        self._queue = queue.Queue(maxsize=5)
        self._upload_thread = threading.Thread(target=self._upload_worker)
        self._upload_started = False

        # 请求相关
        self.headers = {}
        if self.content_type:
            self.headers['Content-Type'] = self.content_type

        # 文件分割上传相关
        self.temp_data = None
        self.uploaded_bytes = 0
        self.file_split_info = {
            'splitFileList': [],
            'meta': {
                'content_length': 0
            }
        }

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
                if self.temp_data is None:
                    chunk = self._queue.get()
                else:
                    chunk = self.temp_data
                if chunk is None:  # None作为结束标志
                    break
                chunk_size = len(chunk)
                if self.uploaded_bytes + chunk_size > FILE_MAX_SIZE:
                    self.temp_data = chunk
                    self._queue.task_done()
                    break
                logger.debug(f"从队列获取数据块: {self.path}, 大小: {len(chunk)}字节")
                self.uploaded_bytes += len(chunk)
                yield chunk
                if self.temp_data is None:
                    self._queue.task_done()
                else:
                    self.temp_data = None
            except Exception as e:
                logger.error(f"从队列获取数据错误: {e}")
                break

    def _upload_worker(self):
        """上传线程函数"""
        try:
            logger.info(f"开始流式上传文件: {self.path}")
            file_folder = self.backend_url.rsplit('/', 1)[0]
            file_name = self.backend_url.rsplit('/', 1)[1]
            file_split_index = 0
            file_last = ''
            while True:
                response = requests.put(
                    file_folder + '/' + file_name + file_last,
                    auth=self.auth,
                    data=self._data_generator(),  # 使用生成器提供数据
                    headers=self.headers
                )
                if response.status_code not in (200, 201, 204, 206):
                    self.error_message = f"上传失败，状态码: {response.status_code}"
                    self.upload_status = self.STATUS_ERROR
                    logger.error(f"上传文件 {file_folder + '/' + file_name + file_last} 失败，状态码: {response.status_code}")
                    break

                self.total_uploaded_bytes += self.uploaded_bytes
                self.file_split_info['splitFileList'].append({
                    'fileName': file_name + file_last,
                    'filesize': self.uploaded_bytes
                })
                self.uploaded_bytes = 0
                file_split_index += 1
                file_last = '.part' + str(file_split_index).zfill(3)

                if self.temp_data is None:
                    break

            # 如果发生了文件分割
            if file_split_index > 1:
                self.file_split_info['meta']['content_length'] = self.total_uploaded_bytes
                split_info = json.dumps(self.file_split_info)
                response = requests.put(file_folder + '/' + file_name + '.splitinfo', auth=self.auth, data=split_info.encode('utf-8'), headers=self.headers)
                if response.status_code not in (200, 201, 204, 206):
                    self.error_message = f"上传分割信息失败，状态码: {response.status_code}"
                    self.upload_status = self.STATUS_ERROR
                    logger.error(f"上传文件 {self.path} 分割信息失败，状态码: {response.status_code}")

            self.upload_status = self.STATUS_DONE
            logger.info(f"文件上传成功: {self.path}, 总大小: {self.total_uploaded_bytes}字节")

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
        self._queue.put(data, block=True)
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
                logger.debug(f"关闭文件上传代理: {self.path}, 已上传数据: {self.total_uploaded_bytes}字节")

    def get_status(self) -> Dict[str, Any]:
        """获取上传状态"""
        return {
            'path': self.path,
            'uploaded_bytes': self.total_uploaded_bytes,
            'status': self.upload_status,
            'closed': self.closed,
            'error': self.error_message
        }


class FileObjectProxy:
    """文件对象代理工厂类 - 根据需要创建下载或上传代理"""

    @staticmethod
    def create_download_proxy(path: str, backend_url: str, auth: Tuple[str, str], 
                             headers: Optional[Dict[str, str]] = None, meta: Optional[Dict[str, Any]] = None) -> FileObjectDownloadProxy:
        """创建下载代理"""
        return FileObjectDownloadProxy(path, backend_url, auth, headers, meta)

    @staticmethod
    def create_upload_proxy(path: str, backend_url: str, auth: Tuple[str, str], 
                           content_type: Optional[str] = None) -> FileObjectUploadProxy:
        """创建上传代理"""
        return FileObjectUploadProxy(path, backend_url, auth, content_type)
