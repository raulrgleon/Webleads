FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd -u 1000 -m app
COPY app.py ./
COPY static ./static
USER 1000:1000
ENV DATA_DIR=/data PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
EXPOSE 3210
CMD ["gunicorn", "--bind", "0.0.0.0:3210", "--workers", "2", "--threads", "2", "--timeout", "90", "--access-logfile", "-", "--error-logfile", "-", "app:app"]
