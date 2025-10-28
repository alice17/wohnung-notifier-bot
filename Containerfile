FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Copy requirements file
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application
COPY inberlinwohnen.py .
COPY settings.json.example /app/settings.json

# Create directory for persistent data
# RUN mkdir -p /app/data 

# Run the application
CMD ["python", "inberlinwohnen.py"]

