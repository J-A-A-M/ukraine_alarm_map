FROM python:3.10.6-alpine
ADD asyncio_cache.py .
ADD requirements.txt .
RUN pip install -r requirements.txt --no-cache-dir && rm -f requirements.txt
CMD python asyncio_cache.py