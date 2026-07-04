FROM python:3.12-slim

# Install system dependencies (e.g., for pymupdf or other parsers if needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install uv for fast package installation
RUN pip install uv

# Copy project definition and install dependencies
COPY pyproject.toml uv.lock ./
RUN uv pip install --system -r pyproject.toml

# Copy backend source code
COPY . .

# Expose port
EXPOSE 8000

# Set production environment
ENV ENVIRONMENT=production

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
