FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y curl ca-certificates && rm -rf /var/lib/apt/lists/*
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY main.py ./
EXPOSE 8088
CMD ["python", "main.py"]