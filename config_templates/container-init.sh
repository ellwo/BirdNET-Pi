#!/bin/bash
set -e

echo "=== BirdNET-Pi Init Container ==="
echo "Running as: $(whoami) (UID:$(id -u) GID:$(id -g))"

# Install assets as birdnetpi user
echo "Installing BirdNET assets..."
cd /opt/birdnetpi
# Use su without dash to preserve PATH environment variable
# shellcheck disable=SC2016
su birdnetpi -c "install-assets install ${BIRDNET_ASSETS_VERSION:-latest} --skip-existing"

# Set up config
echo "Setting up configuration..."
mkdir -p /var/lib/birdnetpi/config

if [ ! -f /var/lib/birdnetpi/config/birdnetpi.yaml ]; then
    echo "Creating initial config from template..."
    cp /opt/birdnetpi/config_templates/birdnetpi.yaml /var/lib/birdnetpi/config/birdnetpi.yaml
else
    echo "Config exists - preserving user settings."
fi

# Fix permissions
echo "Setting ownership to birdnetpi (UID:1000 GID:1000)..."
chown -R 1000:1000 /var/lib/birdnetpi
chmod 755 /var/lib/birdnetpi
chmod 755 /var/lib/birdnetpi/config
chmod 664 /var/lib/birdnetpi/config/birdnetpi.yaml

echo "Permissions set:"
ls -la /var/lib/birdnetpi/config/

# Auto-configure audio devices
echo "Auto-configuring audio devices..."
if [ -f /opt/birdnetpi/config_templates/auto-configure-audio.py ]; then
    # Copy the script to a location where birdnetpi user can access it
    cp /opt/birdnetpi/config_templates/auto-configure-audio.py /var/lib/birdnetpi/auto-configure-audio.py
    chown birdnetpi:birdnetpi /var/lib/birdnetpi/auto-configure-audio.py
    chmod +x /var/lib/birdnetpi/auto-configure-audio.py
    
    # Run auto-configuration as birdnetpi user
    su birdnetpi -c "cd /var/lib/birdnetpi && python3 auto-configure-audio.py"
    
    # Clean up
    rm -f /var/lib/birdnetpi/auto-configure-audio.py
else
    echo "Auto-configuration script not found, using template defaults"
fi

echo "=== Init Complete ==="
