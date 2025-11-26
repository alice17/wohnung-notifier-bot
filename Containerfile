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

# Runtime volumes (must be mounted):
#   - settings.json: Configuration file with Telegram credentials and filters
#   - listings.db:   SQLite database for persisting known listings
#
# Example run command:
#   podman run -d --name wohnung-bot \
#     -v ./settings.json:/app/settings.json:z \
#     -v ./listings.db:/app/listings.db:z \
#     wohnung-scraper

# Run the application
CMD ["python", "main.py"]
