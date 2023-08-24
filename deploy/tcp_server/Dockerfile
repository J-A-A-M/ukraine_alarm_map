FROM python:3.10.6-alpine
ADD asyncio_server.py .
ADD svg_generator.py .
ADD requirements.txt .
RUN pip install -r requirements.txt --no-cache-dir && rm -f requirements.txt
CMD python asyncio_server.py