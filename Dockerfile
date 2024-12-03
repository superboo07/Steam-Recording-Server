# Use the official Python image as a base
FROM python:3.9

# Set the working directory
WORKDIR /app

# Install required system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    openssh-client \
    && rm -rf /var/lib/apt/lists/* 

# Copy application files
COPY . /app

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose the Flask default port
EXPOSE 5000

RUN git pull

# Command to run the application
CMD ["python", "main.py"]
