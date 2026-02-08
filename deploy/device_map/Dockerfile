FROM python:3.13-slim
ENV TZ="Europe/Kyiv"
COPY device_map/device_map.py .
COPY utils.py .
RUN --mount=type=bind,source=device_map/requirements.txt,target=/tmp/requirements.txt \
    python -m pip install --no-cache-dir -r /tmp/requirements.txt
CMD ["python", "device_map.py"]
