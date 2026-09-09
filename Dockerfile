# see.io site contract: plain HTTP on :8080 (the platform terminates TLS).
# State lives ONLY under /data, the volume mounted at runtime.
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8080
# Use the injected $PORT when available, falling back to 8080.
# Use the shell form so the ${PORT:-8080} expansion works inside the container.
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}"]
