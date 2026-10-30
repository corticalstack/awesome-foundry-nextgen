# Pinned to the image python:3.12-slim pointed to on 2026-10-06, as in 08-03. requirements.txt
# is compiled for its glibc (2.41), so recompile it when this changes.
FROM python:3.12.15-slim-trixie
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY authz.py server.py ./
EXPOSE 8080
CMD ["python", "server.py"]
