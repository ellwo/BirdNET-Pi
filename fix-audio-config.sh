#!/bin/bash
# Quick audio configuration fix script
# This script can be run manually or automatically to fix audio device configuration

echo "🔧 BirdNET-Pi Audio Configuration Fix"
echo "=================================="

# Check if we're in a Docker container
if [ ! -f /.dockerenv ]; then
    echo "❌ This script must be run inside the Docker container"
    exit 1
fi

# Check if config file exists
CONFIG_FILE="/var/lib/birdnetpi/config/birdnetpi.yaml"
if [ ! -f "$CONFIG_FILE" ]; then
    echo "❌ Configuration file not found: $CONFIG_FILE"
    exit 1
fi

echo "📝 Current configuration:"
grep -E "(audio_device_index|sample_rate)" "$CONFIG_FILE"

echo ""
echo "🔍 Detecting best audio device..."

# Use Python to detect and configure audio
python3 << 'EOF'
import yaml
import sounddevice as sd
import sys

def find_working_device():
    """Find a working audio input device."""
    try:
        devices = sd.query_devices()
        for i, device in enumerate(devices):
            if device['max_input_channels'] > 0:
                # Test if device works with 48kHz
                try:
                    test_stream = sd.InputStream(device=i, channels=1, samplerate=48000, blocksize=1024)
                    test_stream.close()
                    print(f"✅ Device {i}: {device['name']} - supports 48kHz")
                    return i, 48000
                except:
                    # Try with device's default sample rate
                    try:
                        default_rate = int(device['default_samplerate'])
                        test_stream = sd.InputStream(device=i, channels=1, samplerate=default_rate, blocksize=1024)
                        test_stream.close()
                        print(f"✅ Device {i}: {device['name']} - supports {default_rate}Hz")
                        return i, default_rate
                    except:
                        print(f"❌ Device {i}: {device['name']} - not working")
        return None, None
    except Exception as e:
        print(f"❌ Error detecting devices: {e}")
        return None, None

def update_config(device_index, sample_rate):
    """Update the configuration file."""
    try:
        with open('/var/lib/birdnetpi/config/birdnetpi.yaml', 'r') as f:
            config = yaml.safe_load(f)
        
        config['audio_device_index'] = device_index
        config['sample_rate'] = sample_rate
        
        with open('/var/lib/birdnetpi/config/birdnetpi.yaml', 'w') as f:
            yaml.dump(config, f, default_flow_style=False)
        
        print(f"✅ Configuration updated:")
        print(f"   Audio device: {device_index}")
        print(f"   Sample rate: {sample_rate}Hz")
        return True
    except Exception as e:
        print(f"❌ Error updating config: {e}")
        return False

# Main execution
device_index, sample_rate = find_working_device()
if device_index is not None:
    if update_config(device_index, sample_rate):
        print("🎉 Audio configuration fixed!")
        sys.exit(0)
    else:
        print("❌ Failed to update configuration")
        sys.exit(1)
else:
    print("❌ No working audio devices found")
    sys.exit(1)
EOF

if [ $? -eq 0 ]; then
    echo ""
    echo "🔄 Restarting audio capture service..."
    supervisorctl restart audio_capture
    echo "✅ Audio capture service restarted"
    echo ""
    echo "🎉 Audio configuration is now fixed!"
    echo "   You can now restart the container and it will work automatically."
else
    echo "❌ Failed to fix audio configuration"
    exit 1
fi
