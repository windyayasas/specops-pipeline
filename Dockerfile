FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml README.md ./
COPY specops/ ./specops/
COPY tests/ ./tests/

# Install Python dependencies
RUN pip install --no-cache-dir -e ".[dev]"

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV LOG_LEVEL=INFO

# Default command: CLI
ENTRYPOINT ["python", "-m", "specops"]
CMD ["--help"]
