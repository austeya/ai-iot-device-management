FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY simulator/ ./
EXPOSE 1883
CMD ["python", "app.py"]
