FROM python:3.12-slim

# Install ffmpeg
RUN apt-get update && apt-get install -y ffmpeg

# Set workdir
WORKDIR /app

# Copy code and requirements
COPY . /app
RUN pip install --no-cache-dir -r requirements.txt

# Run bot
CMD ["python", "Mybot.py"]
