FROM python:3.10.6-alpine
ADD map_cache.py .
ADD requirements.txt .
RUN pip install -r requirements.txt --no-cache-dir && rm -f requirements.txt
CMD python map_cache.py