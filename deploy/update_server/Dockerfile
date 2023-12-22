FROM python:3.10.6
ADD update_server.py .
ADD requirements.txt .
ADD ../shared_data/update.bin .
RUN pip install -r requirements.txt --no-cache-dir && rm -f requirements.txt
CMD python update_server.py