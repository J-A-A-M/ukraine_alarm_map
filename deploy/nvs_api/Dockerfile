FROM python:3.12-slim
WORKDIR /app
COPY deploy/nvs_api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY deploy/nvs_api/app.py .
EXPOSE 8765
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8765"]
