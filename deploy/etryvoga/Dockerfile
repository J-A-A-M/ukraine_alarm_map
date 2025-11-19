FROM python:3.12-slim
ENV TZ="Europe/Kyiv"
COPY etryvoga/etryvoga.py .
COPY utils.py .
RUN --mount=type=bind,source=etryvoga/requirements.txt,target=/tmp/requirements.txt \
    python -m pip install --no-cache-dir -r /tmp/requirements.txt
CMD ["python", "etryvoga.py"]