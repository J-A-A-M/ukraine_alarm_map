FROM python:3.13-slim
ENV TZ="Europe/Kyiv"
COPY alerts_http/alerts.py .
COPY utils.py .
RUN --mount=type=bind,source=alerts_http/requirements.txt,target=/tmp/requirements.txt \
    python -m pip install --no-cache-dir -r /tmp/requirements.txt
CMD ["python", "alerts.py"]
