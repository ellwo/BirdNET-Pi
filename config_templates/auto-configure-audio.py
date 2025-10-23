#!/usr/bin/env python3
"""
Automatic Audio Device Configuration for BirdNET-Pi
This script detects the best available audio input device and configures BirdNET-Pi accordingly.
"""

import os
import sys
import yaml
import sounddevice as sd
from pathlib import Path


def find_best_audio_device():
    """Find the best available audio input device."""
    print("🔍 Detecting audio devices...")
    
    try:
        devices = sd.query_devices()
        input_devices = []
        
        for i, device in enumerate(devices):
            if device['max_input_channels'] > 0:
                input_devices.append({
                    'index': i,
                    'name': device['name'],
                    'channels': device['max_input_channels'],
                    'sample_rate': device['default_samplerate']
                })
        
        print(f"Found {len(input_devices)} input devices:")
        for device in input_devices:
            print(f"  Device {device['index']}: {device['name']} ({device['channels']} channels, {device['sample_rate']}Hz)")
        
        # Test each device to find one that works with 48kHz
        working_devices = []
        for device in input_devices:
            try:
                # Test if device supports 48kHz (preferred for bird detection)
                test_stream = sd.InputStream(
                    device=device['index'], 
                    channels=1, 
                    samplerate=48000, 
                    blocksize=1024
                )
                test_stream.close()
                working_devices.append(device)
                print(f"✅ Device {device['index']} supports 48kHz")
            except Exception as e:
                print(f"❌ Device {device['index']} doesn't support 48kHz: {str(e)[:50]}...")
        
        if not working_devices:
            print("⚠️  No devices support 48kHz, trying with default sample rates...")
            for device in input_devices:
                try:
                    test_stream = sd.InputStream(
                        device=device['index'], 
                        channels=1, 
                        samplerate=int(device['sample_rate']), 
                        blocksize=1024
                    )
                    test_stream.close()
                    working_devices.append(device)
                    print(f"✅ Device {device['index']} works with {device['sample_rate']}Hz")
                except Exception as e:
                    print(f"❌ Device {device['index']} failed: {str(e)[:50]}...")
        
        if working_devices:
            # Prefer device 4 (DMIC) if available, otherwise highest sample rate
            device_4 = next((d for d in working_devices if d['index'] == 4), None)
            if device_4:
                print(f"🎯 Selected device 4 (DMIC): {device_4['name']}")
                return device_4['index'], int(device_4['sample_rate'])
            else:
                best_device = max(working_devices, key=lambda d: d['sample_rate'])
                print(f"🎯 Selected device {best_device['index']}: {best_device['name']}")
                return best_device['index'], int(best_device['sample_rate'])
        else:
            print("❌ No working audio devices found!")
            return None, None
            
    except Exception as e:
        print(f"❌ Error detecting audio devices: {e}")
        return None, None


def update_config(device_index, sample_rate):
    """Update the BirdNET-Pi configuration file."""
    config_path = Path('/var/lib/birdnetpi/config/birdnetpi.yaml')
    
    if not config_path.exists():
        print(f"❌ Configuration file not found: {config_path}")
        return False
    
    try:
        # Read current config
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        # Update audio settings
        config['audio_device_index'] = device_index
        config['sample_rate'] = sample_rate
        
        # Write updated config
        with open(config_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)
        
        print(f"✅ Updated configuration:")
        print(f"   Audio device: {device_index}")
        print(f"   Sample rate: {sample_rate}Hz")
        return True
        
    except Exception as e:
        print(f"❌ Error updating configuration: {e}")
        return False


def main():
    """Main function."""
    print("🎤 BirdNET-Pi Audio Auto-Configuration")
    print("=" * 40)
    
    # Check if we're in a Docker container
    if not os.path.exists('/.dockerenv'):
        print("⚠️  This script is designed to run inside a Docker container")
        return 1
    
    # Find best audio device
    device_index, sample_rate = find_best_audio_device()
    
    if device_index is None:
        print("❌ Failed to find a working audio device")
        return 1
    
    # Update configuration
    if update_config(device_index, sample_rate):
        print("🎉 Audio configuration completed successfully!")
        return 0
    else:
        print("❌ Failed to update configuration")
        return 1


if __name__ == '__main__':
    sys.exit(main())
