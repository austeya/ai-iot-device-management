FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app
ENV PYTHONPATH=/app
# System deps for scientific libs (keeps sklearn happy)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential python3-dev gfortran libatlas-base-dev \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src
COPY dashboard ./dashboard

# Default: simulator (compose overrides for dashboard)
CMD ["python", "src/device_simulator.py"]
