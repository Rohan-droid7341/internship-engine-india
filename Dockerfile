FROM python:3.11-slim

WORKDIR /app

# Install lightweight web dependencies
COPY web/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy web app and local fallback data
COPY web/ ./web/
COPY data/ ./data/

ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "uvicorn web.app:app --host 0.0.0.0 --port ${PORT:-8000}"]
