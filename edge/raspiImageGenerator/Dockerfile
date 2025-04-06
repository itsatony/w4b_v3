FROM python:3.9-slim

# Install dependencies - added qemu and binfmt setup
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
    sudo \
    file \
    lsb-release \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Register binfmt handler for ARM binaries
RUN [ -d /proc/sys/fs/binfmt_misc ] && update-binfmts --enable qemu-arm || echo "Binfmt not available, skipping"

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
