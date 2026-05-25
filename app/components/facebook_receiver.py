"""
FacebookReceiver — Python equivalent of FacebookReceiver.ts.
Handles webhook signature verification and message data extraction.
"""

import hashlib
import hmac
import os
from typing import Optional

from app.utils.logger import logger


class FacebookReceiver:
    def __init__(self):
        self.app_secret = os.getenv("FACEBOOK_APP_SECRET", "")
        if not self.app_secret:
            raise ValueError("FACEBOOK_APP_SECRET is required")
        logger.log_info("Facebook_Receiver", "initialize", "FacebookReceiver initialized")

    def verify_signature(self, payload: bytes, signature_header: str) -> bool:
        """Verify HMAC-SHA256 webhook signature from Facebook."""
        if not signature_header or not signature_header.startswith("sha256="):
            logger.log_warn("Facebook_Receiver", "verify_signature",
                            "Missing or invalid signature header", {"signature": signature_header})
            return False
        received = signature_header[len("sha256="):]
        expected = hmac.new(
            self.app_secret.encode("utf-8"), payload, hashlib.sha256
        ).hexdigest()
        try:
            valid = hmac.compare_digest(received, expected)
        except Exception:
            valid = False
        if not valid:
            logger.log_warn("Facebook_Receiver", "verify_signature",
                            "Webhook signature verification failed",
                            {"expected": expected, "received": received})
        return valid

    def extract_message_data(self, body: dict) -> Optional[dict]:
        """
        Extract the first message from a Facebook webhook payload.
        Returns a dict with senderId, content, timestamp — or None if not a message event.
        """
        try:
            if body.get("object") != "page":
                return None
            entries = body.get("entry", [])
            if not entries:
                return None
            messaging = entries[0].get("messaging", [])
            if not messaging:
                return None
            event = messaging[0]

            sender_id = event.get("sender", {}).get("id")
            message = event.get("message", {})
            text = message.get("text")
            timestamp_ms = event.get("timestamp")

            if not sender_id or not text or not timestamp_ms:
                return None

            from datetime import datetime, timezone
            ts = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc).isoformat()

            logger.log_debug("Facebook_Receiver", "extract_message_data",
                             "Message extracted", {"senderId": sender_id})
            return {"senderId": sender_id, "content": text, "timestamp": ts, "history": []}

        except Exception as exc:
            logger.log_error("Facebook_Receiver", "extract_message_data",
                             "Failed to extract message", {"error": exc})
            return None
