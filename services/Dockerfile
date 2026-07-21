FROM python:3.12.9-slim
WORKDIR /app
COPY services/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY services /app/services
ENV PYTHONUNBUFFERED=1 PYTHONPATH=/app
CMD ["sh", "-c", "uvicorn services.${SERVICE_NAME}.app:app --host 0.0.0.0 --port 8000"]

