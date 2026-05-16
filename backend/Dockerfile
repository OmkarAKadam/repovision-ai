FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN pip install uv --no-cache-dir
COPY requirements.txt .
RUN uv pip install -r requirements.txt --system
RUN useradd -m appuser
COPY . backend/
ENV PYTHONPATH=/app
USER appuser
EXPOSE 8080
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1", "--log-level", "info"]
