FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir httpx==0.27.2

COPY seed /app/seed

ENTRYPOINT ["python", "-m", "seed"]
