# ==============================================================================
# Stage 1: Frontend Builder (React + Vite + Tailwind CSS)
# ==============================================================================
FROM node:22-alpine AS frontend-builder

WORKDIR /frontend-v2

COPY frontend-v2/package*.json ./
RUN npm ci

COPY frontend-v2/ ./
RUN npm run build

# ==============================================================================
# Stage 2: Backend Runtime (Python 3.11 + FastAPI + Uvicorn)
# ==============================================================================
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
COPY frontend/ ./frontend/
COPY --from=frontend-builder /frontend-v2/dist ./frontend-v2/dist

RUN mkdir -p /app/data /app/uploads/receipts /app/uploads/temp

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import sys, urllib.request; resp = urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3); sys.exit(0 if resp.status == 200 else 1)"

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
