FROM python:3.9-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy the rest of the application
COPY . .

# Expose the port specified by the PORT environment variable (default 5000)
EXPOSE 443

# Run the bot
CMD ["python", "bot.py"]
