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
    destination_type = "phone"  # "phone" or "group"

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


class WassengerProvider(NotificationProvider):
    """Wassenger WhatsApp API (https://console.wassenger.com/docs/).
    Unlike Meta's Cloud API, Wassenger sends directly to WhatsApp groups
    with no participant cap — this is what lets us drop the per-campaign
    single-number workaround and notify an actual group."""

    destination_type = "group"

    def __init__(self, api_key, device_id=None):
        self.api_key = api_key
        self.device_id = device_id

    def send(self, destination, message):
        """`destination` must be a WhatsApp group JID, e.g. '1203630298136@g.us'."""
        url = "https://api.wassenger.com/v1/messages"
        headers = {
            "Token": self.api_key,
            "Content-Type": "application/json",
        }
        payload = {"group": destination, "message": message}
        if self.device_id:
            payload["device"] = self.device_id

        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=10)
            data = resp.json() if resp.content else {}
        except requests.RequestException as exc:
            logger.error("Wassenger send failed (network): %s", exc)
            return {"success": False, "provider_message_id": None, "error": str(exc)}

        if resp.status_code in (200, 201):
            return {"success": True, "provider_message_id": data.get("id"), "error": None}

        error_msg = data.get("message") or data.get("error") or f"HTTP {resp.status_code}"
        logger.error("Wassenger send failed: %s", error_msg)
        return {"success": False, "provider_message_id": None, "error": error_msg}

def get_whatsapp_provider():
    wassenger_key = os.environ.get("WASSENGER_API_KEY")
    if wassenger_key:
        return WassengerProvider(wassenger_key, os.environ.get("WASSENGER_DEVICE_ID"))

    phone_number_id = os.environ.get("WHATSAPP_PHONE_NUMBER_ID")
    access_token = os.environ.get("WHATSAPP_ACCESS_TOKEN")
    if not phone_number_id or not access_token:
        return LoggingOnlyProvider()
    api_version = os.environ.get("WHATSAPP_API_VERSION", "v21.0")
    return WhatsAppCloudProvider(phone_number_id, access_token, api_version)