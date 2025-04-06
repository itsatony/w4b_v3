FROM python:3.9-slim

# Install dependencies
RUN apt-get update && apt-get install -y \
    xz-utils \
    kpartx \
    parted \
    e2fsprogs \
    dosfstools \
    mount \
    coreutils \
    util-linux \
    qemu-user-static \
    binfmt-support \
    curl \
    wget \
    rsync \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Make scripts executable
RUN chmod +x *.py

# Set entrypoint
ENTRYPOINT ["python3", "image_generator.py"]
