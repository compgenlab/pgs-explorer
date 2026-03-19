FROM python:3.11-slim

WORKDIR /app

# Install dependencies first for better layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app.py .
COPY apps/ apps/
COPY static/ static/
COPY templates/ templates/

# temp/ will be mounted as a volume; create as fallback for local dev
RUN mkdir -p temp

EXPOSE 5001

CMD ["python", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "5001"]
