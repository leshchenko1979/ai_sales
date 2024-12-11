FROM python:3-slim AS builder

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy only requirements first
COPY requirements.txt .

# Install Python dependencies
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /wheels \
    -r requirements.txt python-dotenv

# Final stage
FROM python:3-slim

COPY --from=builder /wheels /wheels
COPY --from=builder /requirements.txt .
RUN pip install --no-cache /wheels/*

# Copy the .env file
COPY .env .

# Copy the jeeves directory
COPY jeeves /jeeves

# Set environment variables
ENV PYTHONPATH=/jeeves
ENV PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /jeeves

# Test imports
RUN python -c "import dotenv; dotenv.load_dotenv('.env'); from main import main; print('Main module imported successfully!')"

# Add Tini
ENV TINI_VERSION v0.19.0
ADD https://github.com/krallin/tini/releases/download/${TINI_VERSION}/tini /tini
RUN chmod +x /tini

# Use tini with subreaper support
ENTRYPOINT ["/tini", "-s", "--"]

# Run Python with proper signal handling
CMD ["python", "-u", "-m", "main"]
