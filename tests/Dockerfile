FROM python:3.12.9-slim
WORKDIR /workspace
COPY control-plane/requirements.txt /tmp/control.txt
COPY services/requirements.txt /tmp/services.txt
RUN pip install --no-cache-dir -r /tmp/control.txt -r /tmp/services.txt pytest==9.1.1 pytest-asyncio==1.4.0 mcp==1.28.1
COPY . /workspace
ENV PYTHONPATH=/workspace/control-plane:/workspace
CMD ["pytest", "tests"]
