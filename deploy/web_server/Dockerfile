FROM python:3.12-slim
ENV TZ="Europe/Kyiv"
COPY web_server.py .
COPY jaam_v1.css .
COPY jaam_v1.js .
RUN --mount=type=bind,source=requirements.txt,target=/tmp/requirements.txt \
    python -m pip install --no-cache-dir -r /tmp/requirements.txt
CMD python web_server.py