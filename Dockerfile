FROM python:3.12-slim

WORKDIR /locus

# Install deps first (layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Build Tailwind CSS
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && curl -sL https://github.com/tailwindlabs/tailwindcss/releases/download/v3.4.17/tailwindcss-linux-x64 \
       -o /usr/local/bin/tailwindcss \
    && chmod +x /usr/local/bin/tailwindcss \
    && apt-get purge -y curl \
    && rm -rf /var/lib/apt/lists/*

COPY tailwind.config.js .
COPY app/ ./app/

RUN tailwindcss -i app/static/input.css -o app/static/styles.css --minify \
    && rm /usr/local/bin/tailwindcss

# Data volume mount point
RUN mkdir -p /data

ENV DATA_DIR=/data
ENV OLLAMA_URL=http://ollama:11434
ENV EMBED_MODEL=nomic-embed-text

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
