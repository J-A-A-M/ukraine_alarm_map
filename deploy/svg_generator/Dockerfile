FROM python:3.12-slim
COPY svg_generator.py .
RUN --mount=type=bind,source=requirements.txt,target=/tmp/requirements.txt \
    apt-get update && apt-get install --no-install-recommends -y libcairo2 && \
    apt-get clean && rm -rf /var/lib/apt/lists/* && \
    python -m pip install --no-cache-dir -r /tmp/requirements.txt
CMD python svg_generator.py