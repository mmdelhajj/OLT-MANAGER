FROM ubuntu:22.04

LABEL maintainer="OLT Manager"
LABEL version="1.3.1"

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Install packages
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    nginx \
    snmp \
    snmp-mibs-downloader \
    curl \
    wget \
    net-tools \
    iproute2 \
    sshpass \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

# Create directories
RUN mkdir -p /opt/olt-manager/backend /var/www/html /etc/olt-manager /var/log/supervisor

# Copy backend
COPY backend/ /opt/olt-manager/backend/

# Copy frontend (built files)
COPY frontend/index.html frontend/asset-manifest.json /var/www/html/
COPY frontend/static/ /var/www/html/static/

# Setup Python environment
WORKDIR /opt/olt-manager/backend
RUN python3 -m venv venv && \
    . venv/bin/activate && \
    pip install --upgrade pip && \
    pip install -r requirements.txt || \
    pip install fastapi uvicorn sqlalchemy python-jose passlib bcrypt python-multipart aiofiles requests paramiko pysnmp

# Configure Nginx
RUN rm -f /etc/nginx/sites-enabled/default
COPY docker/nginx.conf /etc/nginx/sites-available/olt-manager
RUN ln -sf /etc/nginx/sites-available/olt-manager /etc/nginx/sites-enabled/

# Configure Supervisor
COPY docker/supervisord.conf /etc/supervisor/conf.d/olt-manager.conf

# Create data directory for persistent storage
RUN mkdir -p /opt/olt-manager/backend/data

# Expose ports
EXPOSE 80

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:80/ || exit 1

# Start supervisor
CMD ["/usr/bin/supervisord", "-n", "-c", "/etc/supervisor/supervisord.conf"]
