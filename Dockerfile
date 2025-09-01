# Use multi-stage build: Node for assets, Python for app
FROM node:20-alpine AS node-builder
WORKDIR /app
COPY package.json package-lock.json* ./
# Cache npm to speed up rebuilds
RUN --mount=type=cache,target=/root/.npm npm ci --prefer-offline --no-audit
# Copy frontend sources and Vite config
COPY frontend/ frontend/
COPY vite.config.mjs postcss.config.js tailwind.config.js ./
# Include templates so Tailwind can scan content during build
COPY templates/ templates/
# Copy static directory (images, etc.) that Vite may reference
COPY static/ static/
# Build static assets into static/dist with manifest
RUN npm run build

# Python runtime image
FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app

# Minimal runtime utilities (nc for DB wait)
RUN apt-get update && apt-get install -y --no-install-recommends netcat-openbsd && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Copy built Vite assets from Node stage
COPY --from=node-builder /app/static/dist static/dist

# Directory for collectstatic output (served by nginx)
RUN mkdir -p /app/staticfiles

EXPOSE 8000

# Entrypoint runs migrations, collectstatic, and starts Gunicorn
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

CMD ["/entrypoint.sh"]