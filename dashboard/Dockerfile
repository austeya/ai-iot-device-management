# Python-based dashboard container
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Copy requirements file from project root
COPY requirements.txt ./

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the dashboard source code into container
COPY dashboard/ ./

# Expose port for Flask (or similar)
EXPOSE 80

# Run the dashboard
CMD ["python", "app.py"]
