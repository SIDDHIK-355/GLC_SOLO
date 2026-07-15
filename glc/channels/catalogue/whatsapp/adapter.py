"""WhatsApp channel adapter (Meta Cloud API + Twilio Sandbox).

Translates between WhatsApp's wire format and GLC's typed envelopes:
  - on_message(raw) -> ChannelMessage | None   (inbound: WhatsApp -> brain)
  - send(reply)     -> Any                      (outbound: brain -> WhatsApp)

Two "post offices" can carry WhatsApp messages, each with its own letter
style and its own seal:
  - Meta Cloud API : JSON body, seal in X-Hub-Signature-256
  - Twilio Sandbox : form-encoded body, seal in X-Twilio-Signature
"""

from __future__ import annotations

import hmac
import json
import os
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any
from urllib.parse import parse_qs

import httpx

from glc.channels.base import ChannelAdapter
from glc.channels.envelope import ChannelMessage, ChannelReply
from glc.security.allowlists import allowed
from glc.security.trust_level import classify


class Adapter(ChannelAdapter):
    name = "whatsapp"

    # ─────────────── IN: WhatsApp → brain ───────────────
    async def on_message(self, raw: Any) -> ChannelMessage | None:  # type: ignore[override]
        mock = self.config.get("mock")

        # 1. Disconnect: handle cleanly, never raise.
        if mock is not None and mock.pop_disconnect():
            return None

        # 2. Signed parcel ({"raw_body", "headers"}): check the seal first.
        if isinstance(raw, dict) and "raw_body" in raw:
            raw_body = raw["raw_body"]
            headers = raw.get("headers") or {}
            # real gateway lowercases header names; tests use exact case
            twilio_sig = headers.get("X-Twilio-Signature") or headers.get("x-twilio-signature")
            meta_sig = headers.get("X-Hub-Signature-256") or headers.get("x-hub-signature-256")

            if twilio_sig:  # Twilio-style letter: form fields, not JSON
                params = {k: v[0] for k, v in parse_qs(raw_body.decode()).items()}
                if not self._verify_twilio(params, twilio_sig):
                    return None  # fake seal → bin
                return self._twilio_envelope(params)

            if not self._verify_signature(raw_body, meta_sig):
                return None  # unsigned / tampered → reject
            body = json.loads(raw_body)
        else:
            body = raw  # already-parsed webhook dict

        # 3. Dig the sender id + text out of the messy webhook JSON.
        parsed = self._extract(
            body
        )  ##################################### this is the use of the extract ffuction
        if parsed is None:
            return None
        from_id, text, user_handle = parsed

        # 4. Classify trust level (owner / paired / stranger).
        trust = classify("whatsapp", from_id)

        # 5. In a public channel, drop senders who aren't allowed.
        if self.config.get("is_public_channel"):
            ok, _ = allowed("whatsapp", from_id, is_public_channel=True)
            if not ok:
                return None

        # 6. Build the clean envelope the brain understands.
        return ChannelMessage(
            channel="whatsapp",
            channel_user_id=from_id,
            user_handle=user_handle,
            text=text,
            trust_level=trust,
            arrived_at=datetime.now(UTC),
        )

    # ─────────────── OUT: brain → WhatsApp ───────────────
    async def send(self, reply: ChannelReply) -> Any:
        mock = self.config.get("mock")
        # Twilio creds present and no test-mock → real phone path.
        if mock is None and os.environ.get("TWILIO_ACCOUNT_SID"):
            return await self._send_twilio(reply)
        body = self._to_send_body(reply)
        if mock is not None:
            return await mock.send(body)  # rate-limit dict propagates as-is
        return body  # (real Meta HTTP POST would go here)

    # ─────────────── small helpers ───────────────
    def _twilio_envelope(self, params: dict[str, str]) -> ChannelMessage | None:
        """Badge + envelope from Twilio's form fields (WaId, Body, ProfileName)."""
        from_id = params.get("WaId", "")
        if not from_id:
            return None
        trust = classify("whatsapp", from_id)
        if self.config.get("is_public_channel"):
            ok, _ = allowed("whatsapp", from_id, is_public_channel=True)
            if not ok:
                return None
        return ChannelMessage(
            channel="whatsapp",
            channel_user_id=from_id,
            user_handle=params.get("ProfileName") or from_id,
            text=params.get("Body"),
            trust_level=trust,
            arrived_at=datetime.now(UTC),
        )

    def _verify_twilio(self, params: dict[str, str], signature: str) -> bool:
        """True only if the Twilio seal matches (needs auth token + public URL)."""
        token = os.environ.get("TWILIO_AUTH_TOKEN", "")
        url = os.environ.get("TWILIO_WEBHOOK_URL", "")
        if not token or not url:
            return False
        try:
            from twilio.request_validator import RequestValidator

            return bool(RequestValidator(token).validate(url, params, signature))
        except Exception:
            return False

    async def _send_twilio(self, reply: ChannelReply) -> dict[str, Any]:
        """POST the reply to Twilio's Messages API (sandbox)."""
        sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
        token = os.environ.get("TWILIO_AUTH_TOKEN", "")
        sender = os.environ.get("TWILIO_WHATSAPP_FROM", "")
        to = reply.channel_user_id
        form = {
            # WaId comes without the "+", Twilio wants "whatsapp:+<digits>"
            "To": to if to.startswith("whatsapp:") else f"whatsapp:+{to}",
            "From": sender if sender.startswith("whatsapp:") else f"whatsapp:{sender}",
            "Body": reply.text or "",
        }
        url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
        async with httpx.AsyncClient(auth=(sid, token)) as client:
            resp = await client.post(url, data=form)
        try:
            return resp.json()
        except ValueError:
            return {"status": resp.status_code}

    def _verify_signature(self, raw_body: bytes, header: str | None) -> bool:
        """True only if `header` is a valid HMAC-SHA256 of the raw body."""
        if not header:
            return False
        secret = os.environ.get("WHATSAPP_APP_SECRET", "")
        expected = "sha256=" + hmac.new(secret.encode(), raw_body, sha256).hexdigest()
        return hmac.compare_digest(expected, header)

    def _extract(self, body: Any) -> tuple[str, str | None, str] | None:
        """Pull (from_id, text, user_handle) out of a webhook body, or None."""
        try:
            value = body["entry"][0]["changes"][0]["value"]
            message = value["messages"][0]
            from_id = message["from"]
            text = message.get("text", {}).get("body")
            contacts = value.get("contacts") or [{}]
            user_handle = contacts[0].get("profile", {}).get("name", "")
            return from_id, text, user_handle
        except (KeyError, IndexError, TypeError):
            return None

    def _to_send_body(self, reply: ChannelReply) -> dict[str, Any]:
        """Build the exact Cloud API send shape."""
        return {
            "messaging_product": "whatsapp",
            "to": reply.channel_user_id,
            "type": "text",
            "text": {"body": reply.text or ""},
        }
