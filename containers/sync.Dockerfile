# ClawSync Container - Encrypted Synchronization
# Lightweight container for secure P2P file synchronization with encryption

FROM ubuntu:22.04

# Metadata
LABEL maintainer="OpenKrab Community"
LABEL description="ClawSync - Encrypted bidirectional synchronization for OpenClaw ecosystem"
LABEL version="1.0.0"
LABEL repository="https://github.com/openkrab/claw-sync"

# Environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV SYNCTHING_PORT=22000
ENV SYNCTHING_GUI_PORT=8384
ENV GOCRYPTFS_PASSPHRASE=""
ENV DEVICE_ID=""
ENV DEVICE_NAME=""

# Install system dependencies
RUN apt-get update && apt-get install -y \
    # Core utilities
    curl \
    wget \
    jq \
    gnupg2 \
    # Python 3.8+
    python3 \
    python3-pip \
    python3-venv \
    # Syncthing dependencies
    ca-certificates \
    # gocryptfs dependencies
    fuse \
    libssl-dev \
    pkg-config \
    # File monitoring
    inotify-tools \
    # Cleanup
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Syncthing (latest version)
RUN ARCH=$(dpkg --print-architecture) && \
    if [ "$ARCH" = "amd64" ]; then \
        SYNCTHING_ARCH="amd64"; \
    elif [ "$ARCH" = "arm64" ]; then \
        SYNCTHING_ARCH="arm64"; \
    else \
        SYNCTHING_ARCH="386"; \
    fi && \
    curl -L "https://github.com/syncthing/syncthing/releases/download/v1.27.3/syncthing-linux-${SYNCTHING_ARCH}-v1.27.3.tar.gz" | \
    tar -xz -C /usr/local/bin --strip-components=1 syncthing

# Install gocryptfs
RUN ARCH=$(dpkg --print-architecture) && \
    if [ "$ARCH" = "amd64" ]; then \
        GOCRYPTFS_ARCH="amd64"; \
    elif [ "$ARCH" = "arm64" ]; then \
        GOCRYPTFS_ARCH="arm64"; \
    else \
        GOCRYPTFS_ARCH="386"; \
    fi && \
    curl -L "https://github.com/rfjakob/gocryptfs/releases/download/v2.4.0/gocryptfs_${GOCRYPTFS_ARCH}_linux" \
    -o /usr/local/bin/gocryptfs && \
    chmod +x /usr/local/bin/gocryptfs

# Install Python dependencies
COPY requirements.txt /tmp/
RUN pip3 install --no-cache-dir -r /tmp/requirements.txt

# Create application user
RUN useradd --create-home --shell /bin/bash clawsync && \
    mkdir -p /home/clawsync/sync_encrypted && \
    mkdir -p /home/clawsync/sync_mount && \
    mkdir -p /home/clawsync/config && \
    mkdir -p /home/clawsync/logs && \
    chown -R clawsync:clawsync /home/clawsync

# Set working directory
WORKDIR /home/clawsync

# Copy application code
COPY scripts/ /home/clawsync/scripts/
COPY config.yaml /home/clawsync/config/
COPY hooks/ /home/clawsync/hooks/

# Make scripts executable
RUN chmod +x /home/clawsync/scripts/*.py && \
    chmod +x /home/clawsync/hooks/*.sh

# Install Python dependencies in user space
RUN sudo -u clawsync python3 -m pip install --user -r /tmp/requirements.txt

# Create entrypoint script
RUN echo '#!/bin/bash\n\
set -e\n\
\n\
# Check for required environment variables\n\
if [ -z "$DEVICE_ID" ]; then\n\
    echo "Error: DEVICE_ID environment variable required"\n\
    exit 1\n\
fi\n\
\n\
if [ -z "$GOCRYPTFS_PASSPHRASE" ]; then\n\
    echo "Error: GOCRYPTFS_PASSPHRASE environment variable required"\n\
    exit 1\n\
fi\n\
\n\
# Start Syncthing in background\n\
echo "Starting Syncthing..."\n\
sudo -u clawsync /usr/local/bin/syncthing --home=/home/clawsync/config --gui-address=0.0.0.0:8384 &\n\
\n\
# Wait for Syncthing to start\n\
sleep 5\n\
\n\
# Setup encrypted filesystem\n\
echo "Setting up encrypted filesystem..."\n\
if [ ! -d "/home/clawsync/sync_mount/.gocryptfs" ]; then\n\
    sudo -u clawsync /usr/local/bin/gocryptfs -init /home/clawsync/sync_encrypted\n\
fi\n\
\n\
# Mount encrypted filesystem\n\
echo "Mounting encrypted filesystem..."\n\
echo "$GOCRYPTFS_PASSPHRASE" | sudo -u clawsync /usr/local/bin/gocryptfs /home/clawsync/sync_encrypted /home/clawsync/sync_mount\n\
\n\
# Configure device\n\
echo "Configuring device: $DEVICE_ID"\n\
python3 /home/clawsync/scripts/setup_device.py --device-id "$DEVICE_ID" --name "$DEVICE_NAME"\n\
\n\
# Start sync daemon\n\
echo "Starting sync daemon..."\n\
exec python3 /home/clawsync/scripts/sync_daemon.py\n\
' > /usr/local/bin/entrypoint.sh && \
    chmod +x /usr/local/bin/entrypoint.sh

# Expose Syncthing GUI port
EXPOSE 8384

# Expose Syncthing port
EXPOSE 22000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD pgrep -f "syncthing" > /dev/null && pgrep -f "sync_daemon.py" > /dev/null || exit 1

# Volume mounts
VOLUME ["/home/clawsync/sync_encrypted", "/home/clawsync/config", "/home/clawsync/logs"]

# Switch to non-root user
USER clawsync

# Default command
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["--help"]
