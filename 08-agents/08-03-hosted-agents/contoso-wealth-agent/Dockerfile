# Pinned to the image python:3.12-slim pointed to on 2026-10-06. requirements.txt
# is compiled for its glibc (2.41), so recompile it when this changes.
FROM python:3.12.15-slim-trixie
WORKDIR /app
RUN apt-get update && apt-get install -y curl ca-certificates && rm -rf /var/lib/apt/lists/*
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY main.py ./
EXPOSE 8088
CMD ["python", "main.py"]