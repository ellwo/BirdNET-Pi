# BirdNET-Pi Audio Auto-Configuration Solution

## Problem Solved ✅
Your BirdNET-Pi Docker container now automatically configures the correct audio device on startup, eliminating the need for manual configuration after each `docker compose down` and `docker compose up -d`.

## What Was Fixed

### 1. **Template Configuration Updated**
- Modified `/config_templates/birdnetpi.yaml` to use device 4 (DMIC) by default
- This ensures new installations start with a working audio device

### 2. **Auto-Configuration Script Created**
- Created `/config_templates/auto-configure-audio.py` - intelligent audio device detection
- Automatically finds the best available audio input device
- Tests device compatibility with different sample rates
- Updates configuration automatically

### 3. **Container Initialization Enhanced**
- Modified `/config_templates/container-init.sh` to run auto-configuration
- Runs during container startup to ensure proper audio device selection

### 4. **Manual Fix Script Available**
- Created `/fix-audio-config.sh` for manual fixes if needed
- Can be run inside the container to fix audio configuration issues

## How It Works Now

### Automatic Configuration (Default)
When you run `docker compose up -d`, the system will:

1. **Init Container** runs and detects available audio devices
2. **Auto-Configuration** finds the best working audio device
3. **Configuration Update** sets the optimal device and sample rate
4. **Main Container** starts with correct audio settings
5. **Audio Capture** works immediately without errors

### Manual Fix (If Needed)
If you ever need to fix audio configuration manually:

```bash
# Copy the fix script into the container
docker cp fix-audio-config.sh birdnet-pi:/tmp/fix-audio-config.sh

# Run the fix script
docker exec birdnet-pi chmod +x /tmp/fix-audio-config.sh
docker exec birdnet-pi /tmp/fix-audio-config.sh
```

## Current Working Configuration

- **Audio Device**: Device 0 (sof-hda-dsp HDA Analog)
- **Sample Rate**: 48kHz (optimal for bird detection)
- **Channels**: 1 (mono)
- **Status**: ✅ Working perfectly

## Testing Results

✅ **Container Restart Test**: Passed
- `docker compose down` → `docker compose up -d` works automatically
- No manual configuration needed
- Audio capture starts successfully

✅ **Audio Recording Test**: Passed
- Direct audio recording works
- Audio data flows through FIFO pipes
- Bird detection analysis running

## Files Modified/Created

1. **`config_templates/birdnetpi.yaml`** - Updated default audio device
2. **`config_templates/auto-configure-audio.py`** - Auto-detection script
3. **`config_templates/container-init.sh`** - Enhanced initialization
4. **`fix-audio-config.sh`** - Manual fix script

## Usage Instructions

### Normal Operation
```bash
# Start BirdNET-Pi (audio will auto-configure)
docker compose up -d

# Stop BirdNET-Pi
docker compose down

# Restart BirdNET-Pi (audio will auto-configure again)
docker compose up -d
```

### Troubleshooting
If audio issues occur:

1. **Check status**: `docker exec birdnet-pi supervisorctl status audio_capture`
2. **View logs**: `docker logs birdnet-pi --tail 20`
3. **Run fix script**: Use the manual fix script above
4. **Check devices**: `docker exec birdnet-pi python3 -c "import sounddevice as sd; print(sd.query_devices())"`

## Success Indicators

✅ **Audio Capture Service**: `RUNNING` status
✅ **No PortAudio Errors**: Clean startup logs
✅ **Audio Data Flow**: FIFO pipes receiving data
✅ **Web Interface**: Accessible at `http://localhost:8000`

Your BirdNET-Pi is now fully automated and will work correctly every time you restart the container! 🎉🐦
