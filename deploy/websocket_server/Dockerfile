FROM python:3.12-slim
COPY websocket_server.py .
COPY GeoLite2-City.mmdb .
RUN --mount=type=bind,source=requirements.txt,target=/tmp/requirements.txt \
    python -m pip install --no-cache-dir -r /tmp/requirements.txt
CMD python websocket_server.py