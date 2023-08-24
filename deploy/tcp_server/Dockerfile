FROM python:3.10.6
ADD asyncio_server.py .
ADD svg_generator.py .
ADD requirements.txt .
RUN apt-get install libcairo2
RUN pip install -r requirements.txt --no-cache-dir && rm -f requirements.txt
CMD python asyncio_server.py