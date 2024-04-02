FROM python:3.12-slim
ADD websocket_server.py .
ADD GeoLite2-City.mmdb .
ADD requirements.txt .
RUN pip install -r requirements.txt --no-cache-dir && rm -f requirements.txt
CMD python websocket_server.py