FROM python:3.12-slim
ENV TZ="Europe/Kyiv"
COPY ukrenergo/energy.py .
COPY utils.py .
COPY regions.json .
RUN --mount=type=bind,source=ukrenergo/requirements.txt,target=/tmp/requirements.txt \
    python -m pip install --no-cache-dir -r /tmp/requirements.txt
CMD ["python", "energy.py"]