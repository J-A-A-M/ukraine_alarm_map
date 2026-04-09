FROM python:3.13-slim
ENV TZ="Europe/Kyiv"
COPY etryvoga_ws/etryvoga_ws.py .
COPY utils.py .
COPY regions.json .
RUN --mount=type=bind,source=etryvoga_ws/requirements.txt,target=/tmp/requirements.txt \
    python -m pip install --no-cache-dir -r /tmp/requirements.txt
CMD ["python", "etryvoga_ws.py"]
