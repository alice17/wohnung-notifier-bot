FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Copy requirements file
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY src/ /app/src/
COPY data/ /app/data/
COPY main.py .

# Note: settings.json must be mounted as a volume at runtime
# Do not copy settings.json into the image for security and flexibility

# Run the application
CMD ["python", "main.py"]
