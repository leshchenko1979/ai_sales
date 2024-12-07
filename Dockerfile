FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy only requirements first
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy only the jeeves directory
COPY jeeves/ /app/jeeves/

# Set environment variables
ENV PYTHONPATH=/app/jeeves
ENV PYTHONUNBUFFERED=1

# Change to the jeeves directory
WORKDIR /app/jeeves

# Command to run the application
CMD ["python", "main.py"]
