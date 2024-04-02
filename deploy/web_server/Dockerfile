FROM python:3.12-slim
ADD web_server.py .
ADD requirements.txt .
RUN pip install -r requirements.txt --no-cache-dir && rm -f requirements.txt
CMD python web_server.py