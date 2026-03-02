FROM python:3.13-slim
ENV TZ="Europe/Kyiv"
COPY weather/weather.py .
COPY utils.py .
COPY regions.json .
RUN --mount=type=bind,source=weather/requirements.txt,target=/tmp/requirements.txt \
    python -m pip install --no-cache-dir -r /tmp/requirements.txt
CMD ["python", "weather.py"]