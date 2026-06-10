FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-pol \
    tesseract-ocr-eng \
    tesseract-ocr-deu \
    poppler-utils \
    qpdf \
    ghostscript \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}
