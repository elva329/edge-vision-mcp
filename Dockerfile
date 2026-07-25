FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN pip install --no-cache-dir -e src/agui/ 2>/dev/null || true

EXPOSE 9000 8080

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python3 -c "import socket; s=socket.socket(); s.settimeout(2); s.connect(('127.0.0.1', 9000)); s.close()" || exit 1

CMD ["python3", "main.py", "--host", "0.0.0.0", "--port", "9000"]