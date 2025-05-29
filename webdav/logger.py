"""
日志配置模块
"""

import logging
import config

# 日志配置
ENABLE_FILE_LOGGING = config.ENABLE_FILE_LOGGING
LOG_LEVEL = config.LOG_LEVEL
LOG_FILE = config.LOG_FILE

# 配置日志记录器
logger = logging.getLogger('webdav_proxy')

# 防止日志传播到父日志器，避免重复输出
logger.propagate = False

# 清除现有处理程序，防止重复添加
if logger.handlers:
    logger.handlers.clear()

# 设置日志级别
log_level = getattr(logging, LOG_LEVEL, logging.INFO)
logger.setLevel(log_level)

# 创建一个处理器，用于输出到控制台
console_handler = logging.StreamHandler()
console_handler.setLevel(log_level)

# 设置日志格式
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)

# 添加控制台处理器
logger.addHandler(console_handler)

# 如果启用文件日志，添加文件处理器
if ENABLE_FILE_LOGGING:
    file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.info(f'已启用文件日志，日志文件: {LOG_FILE}')
else:
    logger.info('文件日志已禁用，仅输出到控制台')
