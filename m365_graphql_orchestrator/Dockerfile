# -----------------------------------------------------------
# M365 GraphQL Orchestrator — Container image
# -----------------------------------------------------------
FROM python:3.12-slim

# Prevent .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install Python deps
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY prompts/ ./prompts/

# Expose the bot messaging port
EXPOSE 8000

# Run the bot server
CMD ["python", "-m", "src.main"]
