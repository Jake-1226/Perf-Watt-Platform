FROM python:3.11-slim

# Set working directory
WORKDIR /opt/perf-platform

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    wget \
    git \
    sqlite3 \
    net-tools \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r perf-platform && \
    useradd -r -g perf-platform -d /opt/perf-platform -s /bin/bash perf-platform

# Copy application files
COPY . .

# Install Python dependencies
RUN python3 -m venv venv
RUN . venv/bin/pip install --upgrade pip
RUN . venv/bin/pip install -r requirements.txt

# Create necessary directories
RUN mkdir -p data logs backups scripts configs
RUN chown -R perf-platform:perf-platform /opt/perf-platform

# Copy scripts and make executable
RUN cp scripts/*.py scripts/*.sh /opt/perf-platform/scripts/
RUN chmod +x /opt/perf-platform/scripts/*.py /opt/perf-platform/scripts/*.sh

# Set permissions
RUN chown -R perf-platform:perf-platform /opt/perf-platform

# Switch to non-root user
USER perf-platform

# Expose port
EXPOSE 8001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD /opt/perf-platform/health_check.py

# Start the application
CMD ["./venv/bin/python", "run.py", "--host", "0.0.0.0", "--port", "8001"]
