FROM python:3.12.9-slim
WORKDIR /app
COPY control-plane/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY control-plane /app/control-plane
COPY scenarios /app/scenarios
ENV PYTHONUNBUFFERED=1 PYTHONPATH=/app/control-plane
WORKDIR /app/control-plane
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8080"]

