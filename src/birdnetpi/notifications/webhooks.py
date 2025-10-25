"""Webhook service for HTTP-based integrations and notifications.

This service sends HTTP POST requests to configured webhook URLs when
detection events occur, providing integration with external systems.
"""

import asyncio
import base64
import logging
import platform
import socket
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from birdnetpi.detections.models import Detection, DetectionWithTaxa
from birdnetpi.system.status import SystemInspector

logger = logging.getLogger(__name__)


class WebhookConfig:
    """Configuration for a webhook endpoint."""

    def __init__(
        self,
        url: str,
        name: str = "",
        headers: dict[str, str] | None = None,
        enabled: bool = True,
        timeout: int = 10,
        retry_count: int = 3,
        events: list[str] | None = None,
    ) -> None:
        """Initialize webhook configuration.

        Args:
            url: Webhook URL to send POST requests to
            name: Optional descriptive name for the webhook
            headers: Optional HTTP headers to include
            enabled: Whether this webhook is enabled
            timeout: Request timeout in seconds
            retry_count: Number of retry attempts on failure
            events: List of event types to send (default: all)
        """
        self.url = url
        self.name = name or self._extract_name_from_url(url)
        self.headers = headers or {}
        self.enabled = enabled
        self.timeout = timeout
        self.retry_count = retry_count
        self.events = events or ["detection", "health", "gps", "system", "audio_file", "detection_with_taxa"]

        # Validate URL
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError(f"Invalid webhook URL: {url}")

    def _extract_name_from_url(self, url: str) -> str:
        """Extract a name from the webhook URL."""
        parsed = urlparse(url)
        return parsed.netloc or "webhook"

    def should_send_event(self, event_type: str) -> bool:
        """Check if this webhook should receive the given event type."""
        return self.enabled and event_type in self.events


class WebhookService:
    """Service for sending webhook notifications."""

    def __init__(self, enable_webhooks: bool = False, config: Any = None, database_service: Any = None, species_db_service: Any = None, detection_query_service: Any = None) -> None:
        """Initialize webhook service.

        Args:
            enable_webhooks: Whether webhook sending is enabled globally
            config: BirdNET configuration object for accessing site_name and other settings
            database_service: Database service for querying DetectionWithTaxa data
            species_db_service: Species database service for taxonomy lookups
            detection_query_service: Detection query service for enriched detection data
        """
        self.enable_webhooks = enable_webhooks
        self.config = config
        self.database_service = database_service
        self.species_db_service = species_db_service
        self.detection_query_service = detection_query_service
        self.webhooks: list[WebhookConfig] = []
        self.client: httpx.AsyncClient | None = None
        self.stats = {
            "total_sent": 0,
            "total_failed": 0,
            "webhooks_count": 0,
        }

    async def start(self) -> None:
        """Start the webhook service."""
        if not self.enable_webhooks:
            logger.info("Webhook service disabled")
            return

        logger.info("Starting webhook service...")

        # Create HTTP client with reasonable defaults
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0),
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
        )

        logger.info("Webhook service started with %d configured webhooks", len(self.webhooks))

    async def stop(self) -> None:
        """Stop the webhook service."""
        if not self.enable_webhooks:
            return

        logger.info("Stopping webhook service...")

        if self.client:
            await self.client.aclose()
            self.client = None

        logger.info("Webhook service stopped")

    def add_webhook(self, webhook_config: WebhookConfig) -> None:
        """Add a webhook configuration.

        Args:
            webhook_config: Webhook configuration to add
        """
        self.webhooks.append(webhook_config)
        self.stats["webhooks_count"] = len(self.webhooks)
        logger.info("Added webhook: %s (%s)", webhook_config.name, webhook_config.url)

    def remove_webhook(self, url: str) -> bool:
        """Remove a webhook configuration by URL.

        Args:
            url: URL of the webhook to remove

        Returns:
            True if webhook was removed, False if not found
        """
        for i, webhook in enumerate(self.webhooks):
            if webhook.url == url:
                removed = self.webhooks.pop(i)
                self.stats["webhooks_count"] = len(self.webhooks)
                logger.info("Removed webhook: %s (%s)", removed.name, removed.url)
                return True
        return False

    def configure_webhooks_from_urls(self, webhook_urls: list[str]) -> None:
        """Configure webhooks from a list of URLs.

        Args:
            webhook_urls: List of webhook URLs to configure
        """
        self.webhooks.clear()

        for url in webhook_urls:
            if url.strip():  # Skip empty URLs
                try:
                    webhook_config = WebhookConfig(url.strip())
                    self.add_webhook(webhook_config)
                except ValueError as e:
                    logger.error("Invalid webhook URL '%s': %s", url, e)

    async def send_detection_webhook(self, detection: Detection) -> None:
        """Send detection event to configured webhooks.

        Args:
            detection: Detection object to send
        """
        logger.info("===============================")
        logger.info("WEBHOOK: Starting detection webhook process")
        logger.info("===============================")
        
        if not self._can_send():
            logger.warning("===============================")
            logger.warning("WEBHOOK: Cannot send - service disabled or no client")
            logger.warning("===============================")
            return

        logger.info("===============================")
        logger.info("WEBHOOK: Step 1 - Sending detection payload")
        logger.info("===============================")
        
        # Get device identification information
        device_info = self._get_device_info()
        logger.info("WEBHOOK: Device info collected: %s", device_info.get('site_name', 'unknown'))

        # Prepare detection data
        detection_data = {
            "id": str(detection.id),
            "timestamp": detection.timestamp.isoformat(),
            "species": detection.get_display_name(),
            "confidence": detection.confidence,
            "location": {
                "latitude": detection.latitude,
                "longitude": detection.longitude,
            }
            if detection.latitude is not None and detection.longitude is not None
            else None,
            "analysis": {
                "species_confidence_threshold": detection.species_confidence_threshold,
                "week": detection.week,
                "sensitivity_setting": detection.sensitivity_setting,
                "overlap": detection.overlap,
            },
        }

        # Add audio file metadata (without base64 data)
        # audio_file_data = detection.get_audio_file_data()
        # if audio_file_data:
        #     detection_data["audio_file"] = audio_file_data
        #     logger.info("WEBHOOK: Audio file metadata included")

        # Add DetectionWithTaxa data if available
        detection_with_taxa_data = await self._get_detection_with_taxa_data(str(detection.id))
        if detection_with_taxa_data:
            detection_data["detection_with_taxa"] = detection_with_taxa_data
            logger.info("WEBHOOK: DetectionWithTaxa data included")

        payload = {
            "event_type": "detection",
            "timestamp": datetime.now(UTC).isoformat(),
            "device": device_info,
            "detection": detection_data,
        }

        logger.info("WEBHOOK: Payload prepared, size: %d bytes", len(str(payload)))
        await self._send_to_webhooks("detection", payload)
        
        logger.info("===============================")
        logger.info("WEBHOOK: Step 2 - Sending audio file separately")
        logger.info("===============================")
        
        # Send audio file separately if available
        await self._send_audio_file_webhook(detection)

    async def send_detection_with_taxa_webhook(self, detection: DetectionWithTaxa) -> None:
        """Send detection with taxonomy information to configured webhooks.

        Args:
            detection: DetectionWithTaxa object to send
        """
        logger.info("===============================")
        logger.info("WEBHOOK: Starting detection with taxa webhook process")
        logger.info("===============================")
        
        if not self._can_send():
            logger.warning("===============================")
            logger.warning("WEBHOOK: Cannot send - service disabled or no client")
            logger.warning("===============================")
            return

        logger.info("===============================")
        logger.info("WEBHOOK: Step 1 - Sending detection with taxa payload")
        logger.info("===============================")
        
        # Get device identification information
        device_info = self._get_device_info()
        logger.info("WEBHOOK: Device info collected: %s", device_info.get('site_name', 'unknown'))

        # Prepare detection data with taxonomy information
        detection_data = {
            "id": str(detection.id),
            "timestamp": detection.timestamp.isoformat(),
            "species": detection.get_display_name(),
            "confidence": detection.confidence,
            "location": {
                "latitude": detection.latitude,
                "longitude": detection.longitude,
            }
            if detection.latitude is not None and detection.longitude is not None
            else None,
            "analysis": {
                "species_confidence_threshold": detection.species_confidence_threshold,
                "week": detection.week,
                "sensitivity_setting": detection.sensitivity_setting,
                "overlap": detection.overlap,
            },
            "taxonomy": {
                "scientific_name": detection.scientific_name,
                "common_name": detection.common_name,
                "ioc_english_name": detection.ioc_english_name,
                "translated_name": detection.translated_name,
                "family": detection.family,
                "genus": detection.genus,
                "order_name": detection.order_name,
            },
            "first_detection_info": {
                "is_first_ever": detection.is_first_ever,
                "is_first_in_period": detection.is_first_in_period,
                "first_ever_detection": detection.first_ever_detection.isoformat() if detection.first_ever_detection else None,
                "first_period_detection": detection.first_period_detection.isoformat() if detection.first_period_detection else None,
            },
        }

        # Add audio file metadata (without base64 data)
        audio_file_data = detection.get_audio_file_data()
        if audio_file_data:
            detection_data["audio_file"] = audio_file_data
            logger.info("WEBHOOK: Audio file metadata included")

        payload = {
            "event_type": "detection_with_taxa",
            "timestamp": datetime.now(UTC).isoformat(),
            "device": device_info,
            "detection": detection_data,
        }

        logger.info("WEBHOOK: Payload prepared, size: %d bytes", len(str(payload)))
        await self._send_to_webhooks("detection_with_taxa", payload)
        
        logger.info("===============================")
        logger.info("WEBHOOK: Step 2 - Sending audio file separately")
        logger.info("===============================")
        
        # Send audio file separately if available
        await self._send_audio_file_webhook_for_taxa(detection)

    async def _send_audio_file_webhook(self, detection: Detection) -> None:
        """Send audio file separately to configured webhooks.

        Args:
            detection: Detection object containing audio file information
        """
        # Get audio file data safely
        audio_file_data = detection.get_audio_file_data()
        if not audio_file_data:
            logger.info("===============================")
            logger.info("WEBHOOK: No audio file to send")
            logger.info("===============================")
            return

        if not self.config or not getattr(self.config, 'webhook_include_audio_data', False):
            logger.info("===============================")
            logger.info("WEBHOOK: Audio file sending disabled in config")
            logger.info("===============================")
            return

        logger.info("===============================")
        logger.info("WEBHOOK: Preparing audio file for webhook")
        logger.info("===============================")

        try:
            audio_path = Path("/var/lib/birdnetpi/recordings/"+audio_file_data["file_path"])
            if not audio_path.exists():
                logger.warning("===============================")
                logger.warning("WEBHOOK: Audio file does not exist: %s", audio_path)
                logger.warning("===============================")
                return

            logger.info("WEBHOOK: Reading audio file: %s", audio_path)
            with open(audio_path, 'rb') as f:
                audio_data = f.read()
            
            logger.info("WEBHOOK: Audio file size: %d bytes", len(audio_data))
            
            # Encode audio data to base64
            audio_base64 = base64.b64encode(audio_data).decode('utf-8')
            logger.info("WEBHOOK: Audio file encoded to base64, size: %d characters", len(audio_base64))

            # Get device identification information
            device_info = self._get_device_info()

            # Prepare audio file payload
            audio_payload = {
                "event_type": "audio_file",
                "timestamp": datetime.now(UTC).isoformat(),
                "device": device_info,
                "detection_id": str(detection.id),
                "audio_file": {
                    **audio_file_data,
                    "audio_data_base64": audio_base64,
                },
            }

            logger.info("===============================")
            logger.info("WEBHOOK: Sending audio file payload")
            logger.info("WEBHOOK: Payload keys: %s", list(audio_payload.keys()))
            logger.info("WEBHOOK: Detection ID: %s", audio_payload.get("detection_id"))
            logger.info("WEBHOOK: Total payload size: %d bytes", len(str(audio_payload)))
            logger.info("===============================")

            await self._send_to_webhooks("audio_file", audio_payload)
            
            logger.info("===============================")
            logger.info("WEBHOOK: Audio file webhook completed successfully")
            logger.info("===============================")

        except Exception as e:
            logger.error("===============================")
            logger.error("WEBHOOK: Failed to send audio file: %s", e)
            logger.error("===============================")

    async def _send_audio_file_webhook_for_taxa(self, detection: DetectionWithTaxa) -> None:
        """Send audio file separately for DetectionWithTaxa to configured webhooks.

        Args:
            detection: DetectionWithTaxa object containing audio file information
        """
        # Get audio file data safely
        audio_file_data = detection.get_audio_file_data()
        if not audio_file_data:
            logger.info("===============================")
            logger.info("WEBHOOK: No audio file to send for taxa detection")
            logger.info("===============================")
            return

        if not self.config or not getattr(self.config, 'webhook_include_audio_data', False):
            logger.info("===============================")
            logger.info("WEBHOOK: Audio file sending disabled in config")
            logger.info("===============================")
            return

        logger.info("===============================")
        logger.info("WEBHOOK: Preparing audio file for taxa webhook")
        logger.info("===============================")

        try:
            # For DetectionWithTaxa, we need to load the audio file from database
            if not audio_file_data.get("file_path"):
                logger.warning("===============================")
                logger.warning("WEBHOOK: No file path available for taxa detection")
                logger.warning("===============================")
                return

            audio_path = Path("/var/lib/birdnetpi/recordings/" + audio_file_data["file_path"])
            if not audio_path.exists():
                logger.warning("===============================")
                logger.warning("WEBHOOK: Audio file does not exist: %s", audio_path)
                logger.warning("===============================")
                return

            logger.info("WEBHOOK: Reading audio file: %s", audio_path)
            with open(audio_path, 'rb') as f:
                audio_data = f.read()
            
            logger.info("WEBHOOK: Audio file size: %d bytes", len(audio_data))
            
            # Encode audio data to base64
            audio_base64 = base64.b64encode(audio_data).decode('utf-8')
            logger.info("WEBHOOK: Audio file encoded to base64, size: %d characters", len(audio_base64))

            # Get device identification information
            device_info = self._get_device_info()

            # Prepare audio file payload
            audio_payload = {
                "event_type": "audio_file",
                "timestamp": datetime.now(UTC).isoformat(),
                "device": device_info,
                "detection_id": str(detection.id),
                "audio_file": {
                    **audio_file_data,
                    "audio_data_base64": audio_base64,
                },
            }

            logger.info("===============================")
            logger.info("WEBHOOK: Sending audio file payload for taxa")
            logger.info("WEBHOOK: Payload keys: %s", list(audio_payload.keys()))
            logger.info("WEBHOOK: Detection ID: %s", audio_payload.get("detection_id"))
            logger.info("WEBHOOK: Total payload size: %d bytes", len(str(audio_payload)))
            logger.info("===============================")

            await self._send_to_webhooks("audio_file", audio_payload)
            
            logger.info("===============================")
            logger.info("WEBHOOK: Audio file webhook for taxa completed successfully")
            logger.info("===============================")

        except Exception as e:
            logger.error("===============================")
            logger.error("WEBHOOK: Failed to send audio file for taxa: %s", e)
            logger.error("===============================")

    async def send_health_webhook(self, health_data: dict[str, Any]) -> None:
        """Send system health event to configured webhooks.

        Args:
            health_data: System health information
        """
        if not self._can_send():
            return

        payload = {
            "event_type": "health",
            "timestamp": datetime.now(UTC).isoformat(),
            "health": health_data,
        }

        await self._send_to_webhooks("health", payload)

    async def send_gps_webhook(
        self, latitude: float, longitude: float, accuracy: float | None = None
    ) -> None:
        """Send GPS location event to configured webhooks.

        Args:
            latitude: GPS latitude
            longitude: GPS longitude
            accuracy: Optional GPS accuracy in meters
        """
        if not self._can_send():
            return

        payload = {
            "event_type": "gps",
            "timestamp": datetime.now(UTC).isoformat(),
            "location": {
                "latitude": latitude,
                "longitude": longitude,
                "accuracy": accuracy,
            },
        }

        await self._send_to_webhooks("gps", payload)

    async def send_system_webhook(self, system_data: dict[str, Any]) -> None:
        """Send system statistics event to configured webhooks.

        Args:
            system_data: System statistics and information
        """
        if not self._can_send():
            return

        payload = {
            "event_type": "system",
            "timestamp": datetime.now(UTC).isoformat(),
            "system": system_data,
        }

        await self._send_to_webhooks("system", payload)

    async def _send_to_webhooks(self, event_type: str, payload: dict[str, Any]) -> None:
        """Send event payload to all relevant webhooks.

        Args:
            event_type: Type of event being sent
            payload: Event payload to send
        """
        logger.info("===============================")
        logger.info("WEBHOOK: Sending %s event to webhooks", event_type)
        logger.info("===============================")
        
        if not self.client:
            logger.warning("WEBHOOK: No HTTP client available")
            return

        # Filter webhooks that should receive this event type
        relevant_webhooks = [
            webhook for webhook in self.webhooks if webhook.should_send_event(event_type)
        ]

        if not relevant_webhooks:
            logger.warning("===============================")
            logger.warning("WEBHOOK: No webhooks configured for event type: %s", event_type)
            logger.warning("===============================")
            return

        logger.info("WEBHOOK: Found %d relevant webhooks for %s event", len(relevant_webhooks), event_type)
        for webhook in relevant_webhooks:
            logger.info("WEBHOOK: - %s (%s)", webhook.name, webhook.url)

        # Send to all relevant webhooks concurrently
        tasks = [self._send_webhook_request(webhook, payload) for webhook in relevant_webhooks]

        logger.info("WEBHOOK: Sending requests concurrently...")
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Log results
        successful = sum(1 for result in results if result is True)
        failed = len(results) - successful

        self.stats["total_sent"] += successful
        self.stats["total_failed"] += failed

        logger.info("===============================")
        logger.info("WEBHOOK: %s event completed", event_type)
        logger.info("WEBHOOK: %d successful, %d failed", successful, failed)
        logger.info("===============================")

    async def _send_webhook_request(self, webhook: WebhookConfig, payload: dict[str, Any]) -> bool:
        """Send HTTP POST request to a single webhook.

        Args:
            webhook: Webhook configuration
            payload: Payload to send

        Returns:
            True if successful, False otherwise
        """
        if not self.client:
            logger.error("WEBHOOK: No HTTP client available for %s", webhook.name)
            return False

        logger.info("WEBHOOK: Sending to %s (%s)", webhook.name, webhook.url)

        for attempt in range(webhook.retry_count + 1):
            try:
                # Prepare headers
                headers = {
                    "Content-Type": "application/json",
                    "User-Agent": "BirdNET-Pi/1.0",
                    **webhook.headers,
                }

                logger.info("WEBHOOK: Attempt %d/%d for %s", attempt + 1, webhook.retry_count + 1, webhook.name)

                # Send POST request
                response = await self.client.post(
                    webhook.url,
                    json=payload,
                    headers=headers,
                    timeout=webhook.timeout,
                )

                # Check if successful
                if response.status_code < 400:
                    logger.info("===============================")
                    logger.info("WEBHOOK: SUCCESS - %s (HTTP %d)", webhook.name, response.status_code)
                    logger.info("===============================")
                    return True
                else:
                    logger.warning("===============================")
                    logger.warning("WEBHOOK: FAILED - %s (HTTP %d) - %s", webhook.name, response.status_code, response.text[:200])
                    logger.warning("===============================")

            except httpx.TimeoutException:
                logger.warning("===============================")
                logger.warning("WEBHOOK: TIMEOUT (attempt %d/%d): %s", attempt + 1, webhook.retry_count + 1, webhook.name)
                logger.warning("===============================")
            except httpx.RequestError as e:
                logger.warning("===============================")
                logger.warning("WEBHOOK: REQUEST ERROR (attempt %d/%d): %s - %s", attempt + 1, webhook.retry_count + 1, webhook.name, str(e))
                logger.warning("===============================")
            except Exception as e:
                logger.error("===============================")
                logger.error("WEBHOOK: UNEXPECTED ERROR (attempt %d/%d): %s - %s", attempt + 1, webhook.retry_count + 1, webhook.name, str(e))
                logger.error("===============================")

            # Wait before retry (exponential backoff)
            if attempt < webhook.retry_count:
                wait_time = 2**attempt
                logger.info("WEBHOOK: Waiting %d seconds before retry...", wait_time)
                await asyncio.sleep(wait_time)

        logger.error("===============================")
        logger.error("WEBHOOK: FINAL FAILURE after %d attempts: %s", webhook.retry_count + 1, webhook.name)
        logger.error("===============================")
        return False

    def _get_device_info(self) -> dict[str, Any]:
        """Get device identification information for webhook payloads.
        
        Returns:
            Dictionary containing device identification data
        """
        try:
            # Get hostname
            hostname = socket.gethostname()
        except Exception:
            hostname = "unknown"
            
        try:
            # Get device name from system inspector
            device_name = SystemInspector.get_device_name()
        except Exception:
            device_name = hostname
            
        try:
            # Get platform information
            platform_info = platform.platform()
        except Exception:
            platform_info = "unknown"
            
        # Base device info
        device_info = {
            "hostname": hostname,
            "device_name": device_name,
            "platform": platform_info,
            "architecture": platform.machine(),
            "python_version": platform.python_version(),
        }
        
        # Add configuration data if available
        if self.config:
            try:
                device_info["site_name"] = getattr(self.config, "site_name", "BirdNET-Pi")
                latitude = getattr(self.config, "latitude", None)
                longitude = getattr(self.config, "longitude", None)
                birdweather_id = getattr(self.config, "birdweather_id", "")
                
                if latitude is not None:
                    device_info["latitude"] = latitude
                if longitude is not None:
                    device_info["longitude"] = longitude
                if birdweather_id:
                    device_info["birdweather_id"] = birdweather_id
            except Exception:
                pass  # Ignore config access errors
                
        return device_info

    async def _get_detection_with_taxa_data(self, detection_id: str) -> dict[str, Any] | None:
        """Get DetectionWithTaxa data for a given detection ID.
        
        Args:
            detection_id: UUID of the detection
            
        Returns:
            Dictionary with DetectionWithTaxa data or None if not found
        """
        if not self.detection_query_service:
            logger.debug("WEBHOOK: No detection query service available for DetectionWithTaxa lookup")
            return None
            
        try:
            # Use DetectionQueryService to get enriched detection data
            from uuid import UUID
            detection_with_taxa = await self.detection_query_service.get_detection_with_taxa(UUID(detection_id))
            
            if not detection_with_taxa:
                logger.debug("WEBHOOK: No detection found for ID %s", detection_id)
                return None
            
            # Convert DetectionWithTaxa to dictionary format
            return {
                "id": str(detection_with_taxa.id),
                "scientific_name": detection_with_taxa.scientific_name,
                "common_name": detection_with_taxa.common_name,
                "confidence": detection_with_taxa.confidence,
                "timestamp": detection_with_taxa.timestamp.isoformat() if detection_with_taxa.timestamp else None,
                "latitude": detection_with_taxa.latitude,
                "longitude": detection_with_taxa.longitude,
                "species_confidence_threshold": detection_with_taxa.species_confidence_threshold,
                "week": detection_with_taxa.week,
                "sensitivity_setting": detection_with_taxa.sensitivity_setting,
                "overlap": detection_with_taxa.overlap,
                "taxonomy": {
                    "ioc_english_name": detection_with_taxa.ioc_english_name,
                    "translated_name": detection_with_taxa.translated_name,
                    "family": detection_with_taxa.family,
                    "genus": detection_with_taxa.genus,
                    "order_name": detection_with_taxa.order_name,
                },
                "first_detection_info": {
                    "is_first_ever": detection_with_taxa.is_first_ever,
                    "is_first_in_period": detection_with_taxa.is_first_in_period,
                    "first_ever_detection": detection_with_taxa.first_ever_detection.isoformat() if detection_with_taxa.first_ever_detection else None,
                    "first_period_detection": detection_with_taxa.first_period_detection.isoformat() if detection_with_taxa.first_period_detection else None,
                },
            }
                    
        except Exception as e:
            logger.warning("WEBHOOK: Failed to get DetectionWithTaxa data: %s", e)
            return None

    def _can_send(self) -> bool:
        """Check if webhooks can be sent."""
        return self.enable_webhooks and self.client is not None and bool(self.webhooks)

    def get_webhook_status(self) -> dict[str, Any]:
        """Get webhook service status and statistics."""
        return {
            "enabled": self.enable_webhooks,
            "webhook_count": len(self.webhooks),
            "webhooks": [
                {
                    "name": webhook.name,
                    "url": webhook.url,
                    "enabled": webhook.enabled,
                    "events": webhook.events,
                }
                for webhook in self.webhooks
            ],
            "statistics": self.stats.copy(),
        }

    async def test_webhook(self, webhook_url: str) -> dict[str, Any]:
        """Test a webhook URL by sending a test payload.

        Args:
            webhook_url: URL to test

        Returns:
            Test result information
        """
        if not self.client:
            return {"success": False, "error": "Webhook service not started"}

        try:
            # Create temporary webhook config for testing
            test_webhook = WebhookConfig(webhook_url, name="test", timeout=10)

            # Test payload
            test_payload = {
                "event_type": "test",
                "timestamp": datetime.now(UTC).isoformat(),
                "message": "This is a test webhook from BirdNET-Pi",
                "test": True,
            }

            # Send test request
            success = await self._send_webhook_request(test_webhook, test_payload)

            return {
                "success": success,
                "url": webhook_url,
                "timestamp": datetime.now(UTC).isoformat(),
            }

        except Exception as e:
            return {
                "success": False,
                "url": webhook_url,
                "error": str(e),
                "timestamp": datetime.now(UTC).isoformat(),
            }
