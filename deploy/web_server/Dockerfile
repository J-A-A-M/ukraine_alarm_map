FROM python:3.12-slim
ENV TZ="Europe/Kyiv"
COPY web_server/web_server.py .
COPY web_server/jaam_v1.css .
COPY web_server/jaam_v1.js .
COPY web_server/jaam_v2.js .
COPY utils.py .
COPY regions.json .
RUN --mount=type=bind,source=web_server/requirements.txt,target=/tmp/requirements.txt \
    python -m pip install --no-cache-dir -r /tmp/requirements.txt
CMD ["python", "web_server.py"]