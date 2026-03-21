FROM python:3.12-slim

WORKDIR /locus

# Install deps first (layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app
COPY app/ ./app/

# Data volume mount point
RUN mkdir -p /data

ENV DATA_DIR=/data
ENV OLLAMA_URL=http://ollama:11434
ENV EMBED_MODEL=nomic-embed-text

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
