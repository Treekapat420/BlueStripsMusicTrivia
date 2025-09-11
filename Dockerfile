FROM python:3.12-slim

# Make logs flush immediately
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system deps (helps some wheels if needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    pkg-config \
 && rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements.txt .
RUN python -m pip install --upgrade pip && \
    python -m pip install --no-cache-dir -r requirements.txt

# App code
COPY . .

# Start the bot
CMD ["python", "-m", "src.bot"]
