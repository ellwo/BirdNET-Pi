# BirdNET-Pi Webhook API Documentation

## Overview

BirdNET-Pi sends HTTP POST requests to configured webhook URLs when detection events occur. This enables real-time integration with external systems for bird detection monitoring, analysis, and data collection.

## Configuration

### Enable Webhooks

In your `birdnetpi.yaml` configuration file:

```yaml
# Enable webhook notifications
enable_webhooks: true

# Configure webhook URLs (comma-separated or list)
webhook_urls:
  - "https://your-app.com/webhooks/birdnet"
  - "https://another-service.com/api/bird-detections"

# Optional: Include audio data in webhooks (increases payload size significantly)
webhook_include_audio_data: false
```

## Webhook Events

BirdNET-Pi sends different types of events to webhooks:

### 1. Detection Event (`detection`)

Sent when a new bird detection is made.

**Event Type:** `detection`

**Payload Structure:**
```json
{
  "event_type": "detection",
  "timestamp": "2024-01-15T10:30:45.123456Z",
  "device": {
    "hostname": "birdnet-pi-001",
    "device_name": "My Bird Station",
    "platform": "Linux-5.4.0-74-generic-x86_64-with-glibc2.29",
    "architecture": "x86_64",
    "python_version": "3.11.5",
    "site_name": "My Backyard",
    "latitude": 40.7128,
    "longitude": -74.0060,
    "birdweather_id": "BW12345"
  },
  "detection": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "timestamp": "2024-01-15T10:30:45.123456Z",
    "species": "American Robin",
    "confidence": 0.95,
    "location": {
      "latitude": 40.7128,
      "longitude": -74.0060
    },
    "analysis": {
      "species_confidence_threshold": 0.5,
      "week": 25,
      "sensitivity_setting": 1.0,
      "overlap": 0.0
    },
    "audio_file": {
      "id": "audio-file-uuid",
      "file_path": "2024/01/15/American_Robin_20240115_103045.wav",
      "duration_seconds": 3.0,
      "size_bytes": 48000
    },
    "detection_with_taxa": {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "scientific_name": "Turdus migratorius",
      "common_name": "American Robin",
      "confidence": 0.95,
      "timestamp": "2024-01-15T10:30:45.123456Z",
      "latitude": 40.7128,
      "longitude": -74.0060,
      "species_confidence_threshold": 0.5,
      "week": 25,
      "sensitivity_setting": 1.0,
      "overlap": 0.0,
      "taxonomy": {
        "ioc_english_name": "American Robin",
        "translated_name": "Merle d'Amérique",
        "family": "Turdidae",
        "genus": "Turdus",
        "order_name": "Passeriformes"
      },
      "first_detection_info": {
        "is_first_ever": true,
        "is_first_in_period": true,
        "first_ever_detection": "2024-01-15T10:30:45.123456Z",
        "first_period_detection": "2024-01-15T10:30:45.123456Z"
      }
    }
  }
}
```

### 2. Detection with Taxa Event (`detection_with_taxa`)

Sent when enriched detection data with taxonomy information is available.

**Event Type:** `detection_with_taxa`

**Payload Structure:**
```json
{
  "event_type": "detection_with_taxa",
  "timestamp": "2024-01-15T10:30:45.123456Z",
  "device": {
    "hostname": "birdnet-pi-001",
    "device_name": "My Bird Station",
    "platform": "Linux-5.4.0-74-generic-x86_64-with-glibc2.29",
    "architecture": "x86_64",
    "python_version": "3.11.5",
    "site_name": "My Backyard",
    "latitude": 40.7128,
    "longitude": -74.0060,
    "birdweather_id": "BW12345"
  },
  "detection": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "timestamp": "2024-01-15T10:30:45.123456Z",
    "species": "American Robin",
    "confidence": 0.95,
    "location": {
      "latitude": 40.7128,
      "longitude": -74.0060
    },
    "analysis": {
      "species_confidence_threshold": 0.5,
      "week": 25,
      "sensitivity_setting": 1.0,
      "overlap": 0.0
    },
    "taxonomy": {
      "scientific_name": "Turdus migratorius",
      "common_name": "American Robin",
      "ioc_english_name": "American Robin",
      "translated_name": "Merle d'Amérique",
      "family": "Turdidae",
      "genus": "Turdus",
      "order_name": "Passeriformes"
    },
    "first_detection_info": {
      "is_first_ever": true,
      "is_first_in_period": true,
      "first_ever_detection": "2024-01-15T10:30:45.123456Z",
      "first_period_detection": "2024-01-15T10:30:45.123456Z"
    },
    "audio_file": {
      "id": "audio-file-uuid",
      "file_path": "2024/01/15/American_Robin_20240115_103045.wav",
      "duration_seconds": 3.0,
      "size_bytes": 48000
    }
  }
}
```

### 3. Audio File Event (`audio_file`)

Sent separately when audio data is included in webhooks.

**Event Type:** `audio_file`

**Payload Structure:**
```json
{
  "event_type": "audio_file",
  "timestamp": "2024-01-15T10:30:45.123456Z",
  "device": {
    "hostname": "birdnet-pi-001",
    "device_name": "My Bird Station",
    "platform": "Linux-5.4.0-74-generic-x86_64-with-glibc2.29",
    "architecture": "x86_64",
    "python_version": "3.11.5",
    "site_name": "My Backyard",
    "latitude": 40.7128,
    "longitude": -74.0060,
    "birdweather_id": "BW12345"
  },
  "detection_id": "550e8400-e29b-41d4-a716-446655440000",
  "audio_file": {
    "id": "audio-file-uuid",
    "file_path": "2024/01/15/American_Robin_20240115_103045.wav",
    "duration_seconds": 3.0,
    "size_bytes": 48000,
    "audio_data_base64": "UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQAAAAA..."
  }
}
```

### 4. System Health Event (`health`)

Sent periodically with system health information.

**Event Type:** `health`

**Payload Structure:**
```json
{
  "event_type": "health",
  "timestamp": "2024-01-15T10:30:45.123456Z",
  "health": {
    "cpu_usage": 45.2,
    "memory_usage": 67.8,
    "disk_usage": 23.1,
    "temperature": 42.5,
    "uptime": 86400
  }
}
```

### 5. GPS Location Event (`gps`)

Sent when GPS location is updated.

**Event Type:** `gps`

**Payload Structure:**
```json
{
  "event_type": "gps",
  "timestamp": "2024-01-15T10:30:45.123456Z",
  "location": {
    "latitude": 40.7128,
    "longitude": -74.0060,
    "accuracy": 5.0
  }
}
```

### 6. System Statistics Event (`system`)

Sent with system performance statistics.

**Event Type:** `system`

**Payload Structure:**
```json
{
  "event_type": "system",
  "timestamp": "2024-01-15T10:30:45.123456Z",
  "system": {
    "detections_today": 15,
    "detections_total": 1250,
    "species_count": 45,
    "last_detection": "2024-01-15T10:30:45.123456Z",
    "system_load": 1.2,
    "free_space_gb": 45.6
  }
}
```

## HTTP Headers

All webhook requests include these headers:

```
Content-Type: application/json
User-Agent: BirdNET-Pi/1.0
```

## Response Requirements

Your webhook endpoint should:

1. **Return HTTP 200-399** for successful processing
2. **Return HTTP 400-599** for errors (will trigger retries)
3. **Respond within 30 seconds** (timeout limit)
4. **Handle concurrent requests** (multiple detections may arrive simultaneously)

## Retry Logic

BirdNET-Pi implements exponential backoff retry logic:

- **Initial attempts:** 3 retries
- **Backoff:** 2^attempt seconds (1s, 2s, 4s)
- **Timeout:** 10 seconds per request
- **Final failure:** Logged and counted in statistics

## Data Fields Reference

### Device Information
- `hostname`: System hostname
- `device_name`: Configured device name
- `platform`: Operating system information
- `architecture`: CPU architecture
- `python_version`: Python version running BirdNET-Pi
- `site_name`: Configured site/location name
- `latitude`: Configured GPS latitude
- `longitude`: Configured GPS longitude
- `birdweather_id`: BirdWeather station ID (if configured)

### Detection Data
- `id`: Unique detection UUID
- `timestamp`: Detection timestamp (ISO 8601)
- `species`: Common name of detected species
- `confidence`: Detection confidence (0.0-1.0)
- `location`: GPS coordinates of detection
- `analysis`: Analysis parameters used
- `audio_file`: Audio file metadata
- `detection_with_taxa`: Enriched taxonomy data

### Taxonomy Data
- `scientific_name`: Binomial scientific name
- `common_name`: Common name in configured language
- `ioc_english_name`: IOC English name
- `translated_name`: Translated name (if available)
- `family`: Taxonomic family
- `genus`: Taxonomic genus
- `order_name`: Taxonomic order

### First Detection Info
- `is_first_ever`: First detection of this species ever
- `is_first_in_period`: First detection today
- `first_ever_detection`: Timestamp of first ever detection
- `first_period_detection`: Timestamp of first detection today

## Best Practices

1. **Idempotency**: Handle duplicate detections gracefully
2. **Async Processing**: Process webhooks asynchronously to avoid timeouts
3. **Data Validation**: Validate all incoming data before processing
4. **Error Handling**: Log errors and return appropriate HTTP status codes
5. **Rate Limiting**: Implement rate limiting if needed
6. **Security**: Use HTTPS endpoints and validate requests
7. **Monitoring**: Monitor webhook success rates and response times

## Example Webhook Handler

See the companion guide for complete implementation examples.
