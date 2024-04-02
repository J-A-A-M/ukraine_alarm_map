FROM python:3.12-slim
ADD explosions.py .
ADD requirements.txt .
RUN pip install -r requirements.txt --no-cache-dir && rm -f requirements.txt
CMD python explosions.py