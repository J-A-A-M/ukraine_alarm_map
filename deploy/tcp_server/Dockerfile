FROM python:3.10.6
ADD tcp_server.py .
ADD GeoLite2-City.mmdb .
ADD requirements.txt .
RUN pip install -r requirements.txt --no-cache-dir && rm -f requirements.txt
CMD python tcp_server.py