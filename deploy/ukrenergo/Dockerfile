FROM python:3.12-slim
ENV TZ="Europe/Kyiv"
COPY energy.py .
RUN --mount=type=bind,source=requirements.txt,target=/tmp/requirements.txt \
    python -m pip install --no-cache-dir -r /tmp/requirements.txt
CMD python energy.py