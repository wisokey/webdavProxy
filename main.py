from webdav.server import WebDAVServer
import config

def main():
    """主函数"""
    # 创建WebDAV服务器实例
    server = WebDAVServer(
        backend_url=config.BACKEND_URL,
        backend_username=config.BACKEND_USERNAME,
        backend_password=config.BACKEND_PASSWORD,
        auth_username=config.AUTH_USERNAME,
        auth_password=config.AUTH_PASSWORD,
        host=config.HOST,
        port=config.PORT,
        mount_path=config.MOUNT_PATH
    )

    # 启动服务器
    server.start()

if __name__ == "__main__":
    main()
