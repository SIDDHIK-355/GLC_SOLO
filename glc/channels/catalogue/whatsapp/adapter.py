"""WhatsApp channel adapter (Meta Cloud API).

Translates between WhatsApp's wire format and GLC's typed envelopes:
  - on_message(raw) -> ChannelMessage | None   (inbound: WhatsApp -> brain)
  - send(reply)     -> Any                      (outbound: brain -> WhatsApp)

Wire-format reference: Meta Cloud API webhook + Graph send endpoint.
"""

from __future__ import annotations

import hmac
import json
import os
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any

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

        # 2. Signed form ({"raw_body", "headers"}): verify before trusting it.
        if isinstance(raw, dict) and "raw_body" in raw:
            raw_body = raw["raw_body"]
            header = (raw.get("headers") or {}).get("X-Hub-Signature-256")
            if not self._verify_signature(raw_body, header):
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
        body = self._to_send_body(reply)
        mock = self.config.get("mock")
        if mock is not None:
            return await mock.send(body)  # rate-limit dict propagates as-is
        return body  # (real HTTP POST would go here)

    # ─────────────── small helpers ───────────────
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
