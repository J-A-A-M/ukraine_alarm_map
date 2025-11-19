FROM python:3.12-slim
ENV TZ="Europe/Kyiv"
COPY radiation/radiation.py .
RUN --mount=type=bind,source=radiation/requirements.txt,target=/tmp/requirements.txt \
    python -m pip install --no-cache-dir -r /tmp/requirements.txt
CMD ["python", "radiation.py"]