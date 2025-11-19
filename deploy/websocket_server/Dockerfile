FROM python:3.12-slim
ENV TZ="Europe/Kyiv"
COPY websocket_server/websocket_server.py .
COPY websocket_server/GeoLite2-City.mmdb .
COPY utils.py .
RUN --mount=type=bind,source=websocket_server/requirements.txt,target=/tmp/requirements.txt \
    python -m pip install --no-cache-dir -r /tmp/requirements.txt
CMD ["python", "websocket_server.py"]