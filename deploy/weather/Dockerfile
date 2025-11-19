FROM python:3.12-slim
ENV TZ="Europe/Kyiv"
COPY weather/weather.py .
COPY utils.py .
RUN --mount=type=bind,source=weather/requirements.txt,target=/tmp/requirements.txt \
    python -m pip install --no-cache-dir -r /tmp/requirements.txt
CMD ["python", "weather.py"]