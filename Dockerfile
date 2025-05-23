FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir pip setuptools wheel

COPY pyproject.toml .

RUN pip install --no-cache-dir .

COPY . .

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health/live || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
