# ===================================================================
# Ogak USSD Platform — Multi-stage Docker Build
# ===================================================================

# ----- Stage 1: Base -----
FROM python:3.11-slim as base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# ----- Stage 2: Dependencies -----
FROM base as deps

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ----- Stage 3: Development -----
FROM deps as development

COPY . .

# Create logs directory
RUN mkdir -p logs

EXPOSE 8000 8001 8002 8003 8004

# Default command (overridden by docker-compose)
CMD ["uvicorn", "packages.ussd.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ----- Stage 4: Production -----
FROM deps as production

COPY . .

RUN mkdir -p logs

# Create non-root user
RUN groupadd -r ogak && useradd -r -g ogak ogak
RUN chown -R ogak:ogak /app
USER ogak

EXPOSE 8000 8001 8002 8003 8004

CMD ["uvicorn", "packages.ussd.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
