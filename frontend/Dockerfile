# 广东省博物馆讲解 AI 前端（Streamlit）
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
# 国内服务器直连 PyPI 极慢，走清华镜像
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

COPY . .

# Streamlit 容器化必需：headless + 固定端口，非 root 运行更安全
# 显式把 /app 与 HOME 归属给 uid 1000：scp 上传的文件权限可能被 COPY 原样带进镜像，
# 不修正的话运行用户（uid 1000）会读不了应用文件，导致 import 失败 / 权限报错
ENV HOME=/home/streamlit \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

RUN mkdir -p /home/streamlit && chown -R 1000:1000 /app /home/streamlit

EXPOSE 8501

USER 1000

CMD ["streamlit", "run", "app.py", "--server.port=8501"]
