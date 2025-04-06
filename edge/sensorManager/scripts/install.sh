#!/bin/bash
set -e

# Configuration
INSTALL_DIR="/opt/w4b/sensorManager"
CONFIG_DIR="/etc/w4b"
LOG_DIR="/var/log/w4b"
USER="w4b"
GROUP="w4b"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}W4B Sensor Manager Installation Script${NC}"
echo "------------------------------------"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
  echo -e "${RED}Error: Please run as root${NC}"
  exit 1
fi

# Create user and group if they don't exist
if ! getent group $GROUP > /dev/null; then
    echo "Creating group: $GROUP"
    groupadd $GROUP
fi

if ! getent passwd $USER > /dev/null; then
    echo "Creating user: $USER"
    useradd -m -g $GROUP -s /bin/bash $USER
fi

# Create directories
echo "Creating directories..."
mkdir -p $INSTALL_DIR
mkdir -p $CONFIG_DIR
mkdir -p $LOG_DIR

# Install system dependencies
echo "Installing system dependencies..."
apt-get update
apt-get install -y python3 python3-pip python3-venv postgresql-client

# Install TimescaleDB if requested
read -p "Install TimescaleDB locally? (y/n): " install_timescale
if [[ "$install_timescale" =~ ^[Yy]$ ]]; then
    echo "Installing TimescaleDB..."
    # Add TimescaleDB repository
    apt-get install -y gnupg
    echo "deb https://packagecloud.io/timescale/timescaledb/ubuntu/ $(lsb_release -cs) main" > /etc/apt/sources.list.d/timescaledb.list
    wget --quiet -O - https://packagecloud.io/timescale/timescaledb/gpgkey | apt-key add -
    apt-get update
    apt-get install -y timescaledb-2-postgresql-14
    
    # Configure TimescaleDB
    echo "Configuring TimescaleDB..."
    echo "shared_preload_libraries = 'timescaledb'" >> /etc/postgresql/14/main/postgresql.conf
    systemctl restart postgresql
    
    # Create database and user
    echo "Setting up database..."
    sudo -u postgres psql -c "CREATE USER w4b WITH PASSWORD 'w4b_password';"
    sudo -u postgres psql -c "CREATE DATABASE hivedb OWNER w4b;"
    sudo -u postgres psql -d hivedb -c "CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;"
fi

# Copy files
echo "Copying files to installation directory..."
cp -r . $INSTALL_DIR
chown -R $USER:$GROUP $INSTALL_DIR
chown -R $USER:$GROUP $CONFIG_DIR
chown -R $USER:$GROUP $LOG_DIR

# Create a default config if it doesn't exist
if [ ! -f "$CONFIG_DIR/sensor_config.yaml" ]; then
    echo "Creating default configuration..."
    cp $INSTALL_DIR/config/sensor_config.yaml $CONFIG_DIR/
    # Generate a random hive ID if not set
    HIVE_ID="hive_$(cat /dev/urandom | tr -dc 'a-z0-9' | fold -w 8 | head -n 1)"
    sed -i "s/\${HIVE_ID}/$HIVE_ID/g" $CONFIG_DIR/sensor_config.yaml
fi

# Set up Python virtual environment
echo "Setting up Python virtual environment..."
cd $INSTALL_DIR
python3 -m venv venv
$INSTALL_DIR/venv/bin/pip install --upgrade pip
$INSTALL_DIR/venv/bin/pip install -r requirements.txt

# Install systemd service
echo "Installing systemd service..."
cp $INSTALL_DIR/scripts/w4b-sensor-manager.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable w4b-sensor-manager.service

# Initialize database schema
if [[ "$install_timescale" =~ ^[Yy]$ ]]; then
    echo "Initializing database schema..."
    sudo -u $USER $INSTALL_DIR/venv/bin/python $INSTALL_DIR/scripts/setup_timescaledb.py --config $CONFIG_DIR/sensor_config.yaml
fi

echo -e "${GREEN}Installation complete!${NC}"
echo
echo -e "The sensor manager has been installed to: ${YELLOW}$INSTALL_DIR${NC}"
echo -e "Configuration file: ${YELLOW}$CONFIG_DIR/sensor_config.yaml${NC}"
echo -e "Log directory: ${YELLOW}$LOG_DIR${NC}"
echo
echo -e "To start the service: ${YELLOW}systemctl start w4b-sensor-manager${NC}"
echo -e "To check status: ${YELLOW}systemctl status w4b-sensor-manager${NC}"
echo -e "To view logs: ${YELLOW}journalctl -u w4b-sensor-manager -f${NC}"
echo 
echo -e "${GREEN}Done!${NC}"
