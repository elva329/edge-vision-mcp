# Stage 1: Build frontend
FROM node:20-slim AS frontend-builder
WORKDIR /app/src/agui
COPY src/agui/package*.json ./
RUN npm ci
COPY src/agui/. ./
RUN npm run build

# Stage 2: Production runtime
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .
COPY src/ ./src/

COPY --from=frontend-builder /app/src/agui/dist ./src/agui/dist

EXPOSE 9000 8080

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python3 -c "import socket; s=socket.socket(); s.settimeout(2); s.connect(('127.0.0.1', 9000)); s.close()" || exit 1

CMD ["python3", "main.py", "--host", "0.0.0.0", "--port", "9000"]