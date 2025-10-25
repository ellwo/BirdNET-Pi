# Building a BirdNET-Pi Webhook Handler Application

## Overview

This guide shows you how to build a complete webhook handler application that receives BirdNET-Pi detection events and provides APIs for analysis, visualization, and data management.

## Architecture Overview

```
BirdNET-Pi → Webhook Handler → Database → API Server → Frontend/Client Apps
```

## Technology Stack Recommendations

### Backend Options
- **Python**: FastAPI + SQLAlchemy + PostgreSQL
- **Node.js**: Express + Prisma + PostgreSQL  
- **Go**: Gin + GORM + PostgreSQL
- **Java**: Spring Boot + JPA + PostgreSQL

### Frontend Options
- **React**: With Material-UI or Ant Design
- **Vue.js**: With Vuetify or Quasar
- **Angular**: With Angular Material
- **Svelte**: With Svelte Material UI

## Complete Python Implementation

### 1. Project Structure

```
birdnet-webhook-handler/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI application
│   ├── models/                 # Database models
│   │   ├── __init__.py
│   │   ├── detection.py
│   │   ├── device.py
│   │   └── taxonomy.py
│   ├── schemas/                # Pydantic schemas
│   │   ├── __init__.py
│   │   ├── detection.py
│   │   └── webhook.py
│   ├── api/                    # API routes
│   │   ├── __init__.py
│   │   ├── detections.py
│   │   ├── devices.py
│   │   ├── analytics.py
│   │   └── taxonomy.py
│   ├── services/               # Business logic
│   │   ├── __init__.py
│   │   ├── webhook_handler.py
│   │   ├── analytics.py
│   │   └── taxonomy.py
│   └── database/
│       ├── __init__.py
│       └── connection.py
├── requirements.txt
├── docker-compose.yml
├── Dockerfile
└── README.md
```

### 2. Database Models

**app/models/detection.py**
```python
from sqlalchemy import Column, String, Float, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
import uuid
from datetime import datetime

Base = declarative_base()

class Detection(Base):
    __tablename__ = "detections"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id = Column(UUID(as_uuid=True), ForeignKey("devices.id"), nullable=False)
    
    # Detection data
    scientific_name = Column(String(255), nullable=False)
    common_name = Column(String(255), nullable=False)
    confidence = Column(Float, nullable=False)
    timestamp = Column(DateTime, nullable=False)
    
    # Location data
    latitude = Column(Float)
    longitude = Column(Float)
    
    # Analysis parameters
    species_confidence_threshold = Column(Float)
    week = Column(Float)
    sensitivity_setting = Column(Float)
    overlap = Column(Float)
    
    # Taxonomy data
    family = Column(String(255))
    genus = Column(String(255))
    order_name = Column(String(255))
    ioc_english_name = Column(String(255))
    translated_name = Column(String(255))
    
    # First detection flags
    is_first_ever = Column(Boolean, default=False)
    is_first_in_period = Column(Boolean, default=False)
    first_ever_detection = Column(DateTime)
    first_period_detection = Column(DateTime)
    
    # Audio file data
    audio_file_id = Column(String(255))
    audio_file_path = Column(String(500))
    audio_duration_seconds = Column(Float)
    audio_size_bytes = Column(Integer)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    device = relationship("Device", back_populates="detections")
    
    def to_dict(self):
        return {
            "id": str(self.id),
            "device_id": str(self.device_id),
            "scientific_name": self.scientific_name,
            "common_name": self.common_name,
            "confidence": self.confidence,
            "timestamp": self.timestamp.isoformat(),
            "latitude": self.latitude,
            "longitude": self.longitude,
            "family": self.family,
            "genus": self.genus,
            "order_name": self.order_name,
            "is_first_ever": self.is_first_ever,
            "is_first_in_period": self.is_first_in_period,
            "audio_file_path": self.audio_file_path,
            "created_at": self.created_at.isoformat()
        }
```

**app/models/device.py**
```python
from sqlalchemy import Column, String, Float, DateTime, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime

class Device(Base):
    __tablename__ = "devices"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Device identification
    hostname = Column(String(255), nullable=False)
    device_name = Column(String(255))
    site_name = Column(String(255))
    
    # System information
    platform = Column(String(255))
    architecture = Column(String(255))
    python_version = Column(String(50))
    
    # Location
    latitude = Column(Float)
    longitude = Column(Float)
    birdweather_id = Column(String(100))
    
    # Statistics
    total_detections = Column(Integer, default=0)
    species_count = Column(Integer, default=0)
    last_detection = Column(DateTime)
    
    # Metadata
    first_seen = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    detections = relationship("Detection", back_populates="device")
```

### 3. Webhook Handler Service

**app/services/webhook_handler.py**
```python
import logging
from typing import Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.detection import Detection
from app.models.device import Device
from app.schemas.webhook import WebhookPayload

logger = logging.getLogger(__name__)

class WebhookHandlerService:
    def __init__(self, db: Session):
        self.db = db
    
    async def handle_detection_webhook(self, payload: Dict[str, Any]) -> bool:
        """Handle detection webhook payload."""
        try:
            # Extract device information
            device_data = payload.get("device", {})
            device = await self._get_or_create_device(device_data)
            
            # Extract detection data
            detection_data = payload.get("detection", {})
            
            # Create detection record
            detection = Detection(
                device_id=device.id,
                scientific_name=detection_data.get("scientific_name"),
                common_name=detection_data.get("common_name"),
                confidence=detection_data.get("confidence"),
                timestamp=datetime.fromisoformat(detection_data.get("timestamp").replace('Z', '+00:00')),
                latitude=detection_data.get("latitude"),
                longitude=detection_data.get("longitude"),
                species_confidence_threshold=detection_data.get("species_confidence_threshold"),
                week=detection_data.get("week"),
                sensitivity_setting=detection_data.get("sensitivity_setting"),
                overlap=detection_data.get("overlap"),
            )
            
            # Add taxonomy data if available
            taxonomy_data = detection_data.get("taxonomy", {})
            if taxonomy_data:
                detection.family = taxonomy_data.get("family")
                detection.genus = taxonomy_data.get("genus")
                detection.order_name = taxonomy_data.get("order_name")
                detection.ioc_english_name = taxonomy_data.get("ioc_english_name")
                detection.translated_name = taxonomy_data.get("translated_name")
            
            # Add first detection info
            first_detection_info = detection_data.get("first_detection_info", {})
            if first_detection_info:
                detection.is_first_ever = first_detection_info.get("is_first_ever", False)
                detection.is_first_in_period = first_detection_info.get("is_first_in_period", False)
                
                if first_detection_info.get("first_ever_detection"):
                    detection.first_ever_detection = datetime.fromisoformat(
                        first_detection_info["first_ever_detection"].replace('Z', '+00:00')
                    )
                
                if first_detection_info.get("first_period_detection"):
                    detection.first_period_detection = datetime.fromisoformat(
                        first_detection_info["first_period_detection"].replace('Z', '+00:00')
                    )
            
            # Add audio file data
            audio_file = detection_data.get("audio_file")
            if audio_file:
                detection.audio_file_id = audio_file.get("id")
                detection.audio_file_path = audio_file.get("file_path")
                detection.audio_duration_seconds = audio_file.get("duration_seconds")
                detection.audio_size_bytes = audio_file.get("size_bytes")
            
            # Save to database
            self.db.add(detection)
            self.db.commit()
            
            # Update device statistics
            await self._update_device_stats(device)
            
            logger.info(f"Processed detection: {detection.common_name} ({detection.confidence})")
            return True
            
        except Exception as e:
            logger.error(f"Error processing webhook: {e}")
            self.db.rollback()
            return False
    
    async def _get_or_create_device(self, device_data: Dict[str, Any]) -> Device:
        """Get or create device record."""
        hostname = device_data.get("hostname")
        
        device = self.db.query(Device).filter(Device.hostname == hostname).first()
        
        if not device:
            device = Device(
                hostname=hostname,
                device_name=device_data.get("device_name"),
                site_name=device_data.get("site_name"),
                platform=device_data.get("platform"),
                architecture=device_data.get("architecture"),
                python_version=device_data.get("python_version"),
                latitude=device_data.get("latitude"),
                longitude=device_data.get("longitude"),
                birdweather_id=device_data.get("birdweather_id"),
            )
            self.db.add(device)
            self.db.commit()
        else:
            # Update last seen and any changed data
            device.last_seen = datetime.utcnow()
            device.device_name = device_data.get("device_name", device.device_name)
            device.site_name = device_data.get("site_name", device.site_name)
            device.latitude = device_data.get("latitude", device.latitude)
            device.longitude = device_data.get("longitude", device.longitude)
            self.db.commit()
        
        return device
    
    async def _update_device_stats(self, device: Device):
        """Update device statistics."""
        # Count total detections
        total_detections = self.db.query(Detection).filter(Detection.device_id == device.id).count()
        device.total_detections = total_detections
        
        # Count unique species
        species_count = self.db.query(Detection.scientific_name).filter(
            Detection.device_id == device.id
        ).distinct().count()
        device.species_count = species_count
        
        # Update last detection
        last_detection = self.db.query(Detection).filter(
            Detection.device_id == device.id
        ).order_by(Detection.timestamp.desc()).first()
        
        if last_detection:
            device.last_detection = last_detection.timestamp
        
        self.db.commit()
```

### 4. API Routes

**app/api/detections.py**
```python
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta
from app.database.connection import get_db
from app.models.detection import Detection
from app.schemas.detection import DetectionResponse, DetectionListResponse

router = APIRouter(prefix="/api/detections", tags=["detections"])

@router.get("/", response_model=DetectionListResponse)
async def get_detections(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    device_id: Optional[str] = Query(None),
    species: Optional[str] = Query(None),
    family: Optional[str] = Query(None),
    min_confidence: Optional[float] = Query(None, ge=0.0, le=1.0),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    db: Session = Depends(get_db)
):
    """Get detections with filtering options."""
    
    query = db.query(Detection)
    
    # Apply filters
    if device_id:
        query = query.filter(Detection.device_id == device_id)
    if species:
        query = query.filter(Detection.scientific_name.ilike(f"%{species}%"))
    if family:
        query = query.filter(Detection.family == family)
    if min_confidence:
        query = query.filter(Detection.confidence >= min_confidence)
    if start_date:
        query = query.filter(Detection.timestamp >= start_date)
    if end_date:
        query = query.filter(Detection.timestamp <= end_date)
    
    # Get total count
    total = query.count()
    
    # Apply pagination and ordering
    detections = query.order_by(Detection.timestamp.desc()).offset(skip).limit(limit).all()
    
    return DetectionListResponse(
        detections=[detection.to_dict() for detection in detections],
        total=total,
        skip=skip,
        limit=limit
    )

@router.get("/{detection_id}")
async def get_detection(detection_id: str, db: Session = Depends(get_db)):
    """Get a specific detection by ID."""
    detection = db.query(Detection).filter(Detection.id == detection_id).first()
    
    if not detection:
        raise HTTPException(status_code=404, detail="Detection not found")
    
    return detection.to_dict()

@router.get("/stats/summary")
async def get_detection_stats(db: Session = Depends(get_db)):
    """Get detection statistics summary."""
    
    # Total detections
    total_detections = db.query(Detection).count()
    
    # Unique species
    unique_species = db.query(Detection.scientific_name).distinct().count()
    
    # Detections today
    today = datetime.utcnow().date()
    detections_today = db.query(Detection).filter(
        Detection.timestamp >= today
    ).count()
    
    # Top species
    top_species = db.query(
        Detection.scientific_name,
        Detection.common_name,
        db.func.count(Detection.id).label('count')
    ).group_by(
        Detection.scientific_name,
        Detection.common_name
    ).order_by(db.func.count(Detection.id).desc()).limit(10).all()
    
    return {
        "total_detections": total_detections,
        "unique_species": unique_species,
        "detections_today": detections_today,
        "top_species": [
            {
                "scientific_name": species[0],
                "common_name": species[1],
                "count": species[2]
            }
            for species in top_species
        ]
    }
```

**app/api/analytics.py**
```python
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from typing import List, Optional
from datetime import datetime, timedelta
from app.database.connection import get_db
from app.models.detection import Detection

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

@router.get("/species-distribution")
async def get_species_distribution(
    device_id: Optional[str] = Query(None),
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db)
):
    """Get species distribution over time."""
    
    start_date = datetime.utcnow() - timedelta(days=days)
    
    query = db.query(Detection).filter(Detection.timestamp >= start_date)
    
    if device_id:
        query = query.filter(Detection.device_id == device_id)
    
    # Group by species and count
    species_data = query.with_entities(
        Detection.scientific_name,
        Detection.common_name,
        Detection.family,
        Detection.genus,
        func.count(Detection.id).label('count'),
        func.avg(Detection.confidence).label('avg_confidence')
    ).group_by(
        Detection.scientific_name,
        Detection.common_name,
        Detection.family,
        Detection.genus
    ).order_by(func.count(Detection.id).desc()).all()
    
    return [
        {
            "scientific_name": species[0],
            "common_name": species[1],
            "family": species[2],
            "genus": species[3],
            "count": species[4],
            "avg_confidence": float(species[5]) if species[5] else 0
        }
        for species in species_data
    ]

@router.get("/detection-timeline")
async def get_detection_timeline(
    device_id: Optional[str] = Query(None),
    days: int = Query(7, ge=1, le=30),
    interval: str = Query("hour", regex="^(hour|day|week)$"),
    db: Session = Depends(get_db)
):
    """Get detection timeline for charts."""
    
    start_date = datetime.utcnow() - timedelta(days=days)
    
    query = db.query(Detection).filter(Detection.timestamp >= start_date)
    
    if device_id:
        query = query.filter(Detection.device_id == device_id)
    
    # Group by time interval
    if interval == "hour":
        time_group = func.date_trunc('hour', Detection.timestamp)
    elif interval == "day":
        time_group = func.date_trunc('day', Detection.timestamp)
    else:  # week
        time_group = func.date_trunc('week', Detection.timestamp)
    
    timeline_data = query.with_entities(
        time_group.label('time_period'),
        func.count(Detection.id).label('count')
    ).group_by(time_group).order_by(time_group).all()
    
    return [
        {
            "time_period": period[0].isoformat(),
            "count": period[1]
        }
        for period in timeline_data
    ]

@router.get("/family-distribution")
async def get_family_distribution(
    device_id: Optional[str] = Query(None),
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db)
):
    """Get taxonomic family distribution."""
    
    start_date = datetime.utcnow() - timedelta(days=days)
    
    query = db.query(Detection).filter(
        Detection.timestamp >= start_date,
        Detection.family.isnot(None)
    )
    
    if device_id:
        query = query.filter(Detection.device_id == device_id)
    
    family_data = query.with_entities(
        Detection.family,
        Detection.order_name,
        func.count(Detection.id).label('count'),
        func.count(func.distinct(Detection.scientific_name)).label('species_count')
    ).group_by(
        Detection.family,
        Detection.order_name
    ).order_by(func.count(Detection.id).desc()).all()
    
    return [
        {
            "family": family[0],
            "order": family[1],
            "detection_count": family[2],
            "species_count": family[3]
        }
        for family in family_data
    ]

@router.get("/confidence-analysis")
async def get_confidence_analysis(
    device_id: Optional[str] = Query(None),
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db)
):
    """Get confidence score analysis."""
    
    start_date = datetime.utcnow() - timedelta(days=days)
    
    query = db.query(Detection).filter(Detection.timestamp >= start_date)
    
    if device_id:
        query = query.filter(Detection.device_id == device_id)
    
    confidence_stats = query.with_entities(
        func.min(Detection.confidence).label('min_confidence'),
        func.max(Detection.confidence).label('max_confidence'),
        func.avg(Detection.confidence).label('avg_confidence'),
        func.percentile_cont(0.5).within_group(Detection.confidence).label('median_confidence')
    ).first()
    
    # Confidence distribution
    confidence_ranges = [
        (0.0, 0.2, "Very Low"),
        (0.2, 0.4, "Low"),
        (0.4, 0.6, "Medium"),
        (0.6, 0.8, "High"),
        (0.8, 1.0, "Very High")
    ]
    
    distribution = []
    for min_conf, max_conf, label in confidence_ranges:
        count = query.filter(
            Detection.confidence >= min_conf,
            Detection.confidence < max_conf
        ).count()
        distribution.append({
            "range": label,
            "min": min_conf,
            "max": max_conf,
            "count": count
        })
    
    return {
        "statistics": {
            "min_confidence": float(confidence_stats[0]) if confidence_stats[0] else 0,
            "max_confidence": float(confidence_stats[1]) if confidence_stats[1] else 0,
            "avg_confidence": float(confidence_stats[2]) if confidence_stats[2] else 0,
            "median_confidence": float(confidence_stats[3]) if confidence_stats[3] else 0
        },
        "distribution": distribution
    }
```

### 5. Main Application

**app/main.py**
```python
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from app.database.connection import get_db, engine
from app.models import detection, device
from app.api import detections, analytics, devices
from app.services.webhook_handler import WebhookHandlerService
from app.schemas.webhook import WebhookPayload
import logging

# Create database tables
detection.Base.metadata.create_all(bind=engine)

# Initialize FastAPI app
app = FastAPI(
    title="BirdNET-Pi Webhook Handler",
    description="API for handling BirdNET-Pi detection webhooks and providing analytics",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(detections.router)
app.include_router(analytics.router)
app.include_router(devices.router)

@app.post("/webhooks/birdnet")
async def handle_birdnet_webhook(
    payload: WebhookPayload,
    db: Session = Depends(get_db)
):
    """Handle incoming BirdNET-Pi webhook."""
    
    webhook_handler = WebhookHandlerService(db)
    
    try:
        success = await webhook_handler.handle_detection_webhook(payload.dict())
        
        if success:
            return {"status": "success", "message": "Webhook processed successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to process webhook")
            
    except Exception as e:
        logging.error(f"Webhook processing error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "birdnet-webhook-handler"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

### 6. Docker Configuration

**docker-compose.yml**
```yaml
version: '3.8'

services:
  webhook-handler:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://user:password@db:5432/birdnet_db
    depends_on:
      - db
    volumes:
      - ./logs:/app/logs

  db:
    image: postgres:15
    environment:
      - POSTGRES_DB=birdnet_db
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

volumes:
  postgres_data:
```

**Dockerfile**
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**requirements.txt**
```
fastapi==0.104.1
uvicorn[standard]==0.24.0
sqlalchemy==2.0.23
psycopg2-binary==2.9.9
pydantic==2.5.0
python-multipart==0.0.6
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
alembic==1.13.0
redis==5.0.1
celery==5.3.4
```

## Frontend Implementation

### React Dashboard Example

**src/components/DetectionDashboard.jsx**
```jsx
import React, { useState, useEffect } from 'react';
import {
  Card,
  CardContent,
  Typography,
  Grid,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Chip,
  Box
} from '@mui/material';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';

const DetectionDashboard = () => {
  const [detections, setDetections] = useState([]);
  const [stats, setStats] = useState({});
  const [timeline, setTimeline] = useState([]);
  const [speciesDistribution, setSpeciesDistribution] = useState([]);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      // Fetch recent detections
      const detectionsResponse = await fetch('/api/detections?limit=10');
      const detectionsData = await detectionsResponse.json();
      setDetections(detectionsData.detections);

      // Fetch statistics
      const statsResponse = await fetch('/api/detections/stats/summary');
      const statsData = await statsResponse.json();
      setStats(statsData);

      // Fetch timeline data
      const timelineResponse = await fetch('/api/analytics/detection-timeline?days=7&interval=day');
      const timelineData = await timelineResponse.json();
      setTimeline(timelineData);

      // Fetch species distribution
      const speciesResponse = await fetch('/api/analytics/species-distribution?days=30');
      const speciesData = await speciesResponse.json();
      setSpeciesDistribution(speciesData.slice(0, 10));
    } catch (error) {
      console.error('Error fetching data:', error);
    }
  };

  const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#8884D8'];

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h4" gutterBottom>
        Bird Detection Dashboard
      </Typography>

      {/* Statistics Cards */}
      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Typography color="textSecondary" gutterBottom>
                Total Detections
              </Typography>
              <Typography variant="h4">
                {stats.total_detections || 0}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Typography color="textSecondary" gutterBottom>
                Unique Species
              </Typography>
              <Typography variant="h4">
                {stats.unique_species || 0}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Typography color="textSecondary" gutterBottom>
                Today's Detections
              </Typography>
              <Typography variant="h4">
                {stats.detections_today || 0}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Typography color="textSecondary" gutterBottom>
                Active Devices
              </Typography>
              <Typography variant="h4">
                1
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Charts */}
      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Detection Timeline (7 Days)
              </Typography>
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={timeline}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="time_period" />
                  <YAxis />
                  <Tooltip />
                  <Line type="monotone" dataKey="count" stroke="#8884d8" strokeWidth={2} />
                </LineChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Top Species (30 Days)
              </Typography>
              <ResponsiveContainer width="100%" height={300}>
                <PieChart>
                  <Pie
                    data={speciesDistribution}
                    cx="50%"
                    cy="50%"
                    labelLine={false}
                    label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                    outerRadius={80}
                    fill="#8884d8"
                    dataKey="count"
                  >
                    {speciesDistribution.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Recent Detections Table */}
      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Recent Detections
          </Typography>
          <TableContainer component={Paper}>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Species</TableCell>
                  <TableCell>Confidence</TableCell>
                  <TableCell>Family</TableCell>
                  <TableCell>Timestamp</TableCell>
                  <TableCell>First Detection</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {detections.map((detection) => (
                  <TableRow key={detection.id}>
                    <TableCell>
                      <Typography variant="body2" fontWeight="bold">
                        {detection.common_name}
                      </Typography>
                      <Typography variant="caption" color="textSecondary">
                        {detection.scientific_name}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={`${(detection.confidence * 100).toFixed(1)}%`}
                        color={detection.confidence > 0.8 ? 'success' : detection.confidence > 0.6 ? 'warning' : 'error'}
                        size="small"
                      />
                    </TableCell>
                    <TableCell>{detection.family}</TableCell>
                    <TableCell>
                      {new Date(detection.timestamp).toLocaleString()}
                    </TableCell>
                    <TableCell>
                      {detection.is_first_ever && (
                        <Chip label="First Ever" color="primary" size="small" />
                      )}
                      {detection.is_first_in_period && (
                        <Chip label="First Today" color="secondary" size="small" />
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </CardContent>
      </Card>
    </Box>
  );
};

export default DetectionDashboard;
```

## Deployment Instructions

### 1. Local Development Setup

```bash
# Clone and setup
git clone <your-repo>
cd birdnet-webhook-handler

# Install dependencies
pip install -r requirements.txt

# Setup database
createdb birdnet_db
alembic upgrade head

# Run the application
uvicorn app.main:app --reload
```

### 2. Production Deployment

```bash
# Build and run with Docker
docker-compose up -d

# Configure BirdNET-Pi webhook URL
# In birdnetpi.yaml:
webhook_urls: ["http://your-server:8000/webhooks/birdnet"]
```

### 3. Environment Variables

```bash
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/birdnet_db

# Redis (for caching)
REDIS_URL=redis://localhost:6379

# Security
SECRET_KEY=your-secret-key
JWT_SECRET=your-jwt-secret

# Logging
LOG_LEVEL=INFO
```

## API Endpoints Summary

### Detection Endpoints
- `GET /api/detections/` - List detections with filtering
- `GET /api/detections/{id}` - Get specific detection
- `GET /api/detections/stats/summary` - Get detection statistics

### Analytics Endpoints
- `GET /api/analytics/species-distribution` - Species distribution data
- `GET /api/analytics/detection-timeline` - Timeline charts data
- `GET /api/analytics/family-distribution` - Taxonomic family data
- `GET /api/analytics/confidence-analysis` - Confidence score analysis

### Device Endpoints
- `GET /api/devices/` - List all devices
- `GET /api/devices/{id}` - Get specific device
- `GET /api/devices/{id}/detections` - Get device detections

### Webhook Endpoint
- `POST /webhooks/birdnet` - Receive BirdNET-Pi webhooks

This comprehensive implementation provides a complete webhook handling system with analytics, visualization, and API capabilities for BirdNET-Pi detection data.
