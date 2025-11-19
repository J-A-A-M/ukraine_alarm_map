FROM python:3.12-slim
ENV TZ="Europe/Kyiv"
COPY update_server/update_server.py .
COPY utils.py .
COPY regions.json .
RUN --mount=type=bind,source=update_server/requirements.txt,target=/tmp/requirements.txt \
    python -m pip instal/l --no-cache-dir -r /tmp/requirements.txt
CMD ["python", "update_server.py"]