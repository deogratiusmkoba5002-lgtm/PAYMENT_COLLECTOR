"""
Notification provider abstraction. WhatsApp today; SMS/Email/Telegram can
be added here later as new classes without touching payments or models.

IMPORTANT: WhatsApp's Cloud API "Groups" feature caps groups at 8
participants and requires an Official Business Account, so it is not
usable for campaigns with more contributors than that. This provider
sends to a single WhatsApp phone number instead (the campaign owner's
number by default) — the same numbered-feed message format just goes to
one person, who can forward/share it like a group update.
"""
import os
import logging
import requests

logger = logging.getLogger("notifications")


class NotificationProvider:
    def send(self, destination, message):
        """Returns {'success': bool, 'provider_message_id': str|None, 'error': str|None}"""
        raise NotImplementedError


class LoggingOnlyProvider(NotificationProvider):
    """Used until WHATSAPP_ACCESS_TOKEN / WHATSAPP_PHONE_NUMBER_ID are set
    (e.g. pending Meta Business verification). Never actually sends."""

    def send(self, destination, message):
        logger.info("[WhatsApp NOT CONFIGURED] Would send to %s:\n%s", destination, message)
        return {"success": False, "provider_message_id": None, "error": "WhatsApp credentials not configured"}


class WhatsAppCloudProvider(NotificationProvider):
    """Official Meta WhatsApp Cloud API."""

    def __init__(self, phone_number_id, access_token, api_version="v21.0"):
        self.phone_number_id = phone_number_id
        self.access_token = access_token
        self.api_version = api_version

    def send(self, destination, message):
        url = f"https://graph.facebook.com/{self.api_version}/{self.phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        payload = {
            "messaging_product": "whatsapp",
            "to": destination,
            "type": "text",
            "text": {"body": message},
        }
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=10)
            data = resp.json()
        except requests.RequestException as exc:
            logger.error("WhatsApp send failed (network): %s", exc)
            return {"success": False, "provider_message_id": None, "error": str(exc)}

        if resp.status_code == 200 and data.get("messages"):
            return {"success": True, "provider_message_id": data["messages"][0].get("id"), "error": None}

        error_msg = data.get("error", {}).get("message", f"HTTP {resp.status_code}")
        logger.error("WhatsApp send failed: %s", error_msg)
        return {"success": False, "provider_message_id": None, "error": error_msg}


def get_whatsapp_provider():
    phone_number_id = os.environ.get("WHATSAPP_PHONE_NUMBER_ID")
    access_token = os.environ.get("WHATSAPP_ACCESS_TOKEN")
    if not phone_number_id or not access_token:
        return LoggingOnlyProvider()
    api_version = os.environ.get("WHATSAPP_API_VERSION", "v21.0")
    return WhatsAppCloudProvider(phone_number_id, access_token, api_version)