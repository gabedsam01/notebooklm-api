FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_HOST=0.0.0.0 \
    APP_PORT=8080

WORKDIR /app

COPY pyproject.toml README.md /app/
COPY app /app/app

RUN python -m pip install --upgrade pip && \
    pip install --no-cache-dir .

RUN mkdir -p /app/data/jobs /app/data/artifacts /app/data/auth /app/data/tmp /app/data/run

EXPOSE 8080

VOLUME ["/app/data"]

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
