FROM python:3.12-alpine

WORKDIR /app

# 复制应用程序文件
COPY . /app

# 安装依赖项
RUN pip install --no-cache-dir -r requirements.txt

# 将 config.yaml 声明为数据卷，以便可以从主机挂载
# 这里假设 config.yaml 位于应用程序的根目录 (在容器中是 /app/config.yaml)
VOLUME /app/config.yaml

# 暴露端口 8080 (应用程序的默认端口)
EXPOSE 8080

# 运行应用程序的命令
# 将 `your_main_script.py` 替换为应用程序的实际入口点
CMD ["python", "main.py"]
