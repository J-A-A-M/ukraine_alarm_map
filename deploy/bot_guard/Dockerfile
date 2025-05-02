FROM python:3.12-slim
ENV TZ="Europe/Kyiv"
COPY main.py .
COPY questions.yaml .
COPY config.yaml .
RUN --mount=type=bind,source=requirements.txt,target=/tmp/requirements.txt \
    python -m pip install --no-cache-dir -r /tmp/requirements.txt
CMD ["python", "main.py"]