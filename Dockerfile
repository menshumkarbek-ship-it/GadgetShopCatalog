# Use an explicit lightweight optimized official Python image layer
FROM python:3.12-slim

# Prevent Python from writing pyc cache dumps to tracking disks
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Establish isolated internal workspace folder
WORKDIR /app

# Install native compilation requirements for packages like psycopg2 or Pillow
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Pipe dependencies tracking configuration files internally
COPY requirements.txt /app/

# Install execution layer modules globally inside container spaces
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy absolute current directory workspace contents internally
COPY . /app/

# Production entrypoint. docker-compose overrides this with the dev server;
# a host that runs the image as-is gets gunicorn, with static files already
# collected so WhiteNoise can serve them.
RUN SECRET_KEY=build-only DEBUG=True python manage.py collectstatic --no-input

# Run as an unprivileged user, not root. It owns /app so local media uploads
# (used when no R2 bucket is configured) can still be written.
RUN useradd --create-home --uid 1000 app && chown -R app:app /app
USER app

EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "60"]
