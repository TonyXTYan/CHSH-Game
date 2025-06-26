# Use the official Python image as the base image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Copy only the requirements file first (for better caching)
COPY requirements.txt .

# Install dependencies in a single RUN command to reduce layers
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir gunicorn eventlet

# Copy the application code (excluding files in .dockerignore)
COPY . .

# Expose the port the app runs on
EXPOSE 8080

# Set the command to run the application
CMD ["gunicorn", "wsgi:app", "--worker-class", "eventlet", "--bind", "0.0.0.0:8080"]
