# Use the official Python image as the base image
FROM python:3.11-slim

# Set up a non-root user and home directory
RUN useradd -ms /bin/bash ubuntu
USER ubuntu
WORKDIR /home/ubuntu

# Copy only requirements and install dependencies
# COPY requirements.txt requirements.txt
# RUN pip install --no-cache-dir --upgrade pip \
#     && pip install --no-cache-dir -r requirements.txt

# Install any additional dev tools you need here
# RUN pip install <dev-tools>

# Do NOT copy the application code

# # Install gunicorn and eventlet
# RUN pip install gunicorn eventlet

# # Expose the port the app runs on
# EXPOSE 8080

# # Set the command to run the application
# CMD ["gunicorn", "wsgi:app", "--worker-class", "eventlet"]
