FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    libspatialindex-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .

RUN pip install --no-cache-dir -e .

COPY . .

CMD ["uvicorn", "geostride.main:app", "--host", "0.0.0.0", "--port", "8000"]
