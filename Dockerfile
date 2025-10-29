FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app
ENV PYTHONPATH=/app

# Use OpenBLAS on Debian trixie (ATLAS is gone)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential python3-dev gfortran libopenblas-dev \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# bring your code
COPY src ./src
COPY dashboard ./dashboard
