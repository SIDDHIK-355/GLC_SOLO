# WhatsApp channel adapter (Meta Cloud API)

A GLC channel adapter that connects **WhatsApp** to the gateway. It translates
WhatsApp's webhook/wire format into GLC's typed envelopes in both directions and
enforces the trust boundary before any message reaches the agent.

- **Slot:** `whatsapp`  ·  **Group:** WhatsApp
- **Provider:** Meta WhatsApp Cloud API (webhook in, Graph send endpoint out)

---

## What it does

Two methods, both speaking only the canonical envelopes from
`glc.channels.envelope` — the agent never sees raw WhatsApp JSON:

| Method | Direction | Produces / consumes |
|--------|-----------|---------------------|
| `on_message(raw)` | inbound (WhatsApp → agent) | returns `ChannelMessage` (or `None` to reject) |
| `send(reply)`     | outbound (agent → WhatsApp) | consumes `ChannelReply`, returns the API result |

---

## Architecture

```
WhatsApp ──webhook──►  on_message ──► [disconnect? signature? parse? trust? allowlist?] ──► ChannelMessage ──► agent
                                                                                                                │
WhatsApp ◄──send API──  send  ◄── [build Cloud-API body] ◄─────────────────────────────────── ChannelReply ◄──┘
```

**`on_message`** runs six ordered steps:

1. **Disconnect** — if the mock signals a dropped connection, return cleanly (never raise).
2. **Signature** — for signed webhooks (`{"raw_body", "headers"}`), verify the
   `X-Hub-Signature-256` HMAC **before** building anything; reject if invalid.
3. **Parse** — pull `from_id`, `text`, and the profile name out of the nested webhook JSON.
4. **Trust level** — `glc.security.trust_level.classify()` →
   `owner_paired` / `user_paired` / `untrusted`.
5. **Allowlist** — in a public-channel context, drop senders who aren't allowed
   (`glc.security.allowlists.allowed`).
6. **Build** — assemble and return a typed `ChannelMessage`.

**`send`** builds the exact Cloud API body and dispatches it (via the injected
mock in tests, or a real HTTP POST in production). A rate-limit response is
returned to the caller unchanged.

Three private helpers keep the methods readable:
`_verify_signature`, `_extract`, `_to_send_body`.

> `schemas.py` is intentionally empty — this adapter needs no channel-specific
> Pydantic types; the canonical envelope and plain dicts are sufficient.

---

## Setup & credentials

For real (non-test) use, the adapter expects these environment variables:

| Variable | Purpose |
|----------|---------|
| `WHATSAPP_APP_SECRET` | secret used to verify the `X-Hub-Signature-256` webhook signature |
| `WHATSAPP_PHONE_NUMBER_ID` | the sending phone-number id (Graph send endpoint) |
| `WHATSAPP_TOKEN` | bearer token for the Graph API |

Free tier: Meta WhatsApp Cloud API allows 1,000 free service conversations/month.

---

## Channel quirks (things specific to WhatsApp)

- **Signed webhooks.** Every real inbound webhook carries
  `X-Hub-Signature-256: sha256=<hex>` — an HMAC-SHA256 of the **raw** request
  body using the app secret. The adapter verifies this and **refuses to build an
  envelope** for unsigned or tampered payloads. This is the load-bearing security
  behaviour for the channel.
- **E.164 ids without `+`.** WhatsApp ids (`wa_id`) are E.164 numbers with no
  leading `+` (e.g. `919999990000`). They are used directly as `channel_user_id`.
- **Nested send shape.** The send body must nest text under `text.body`:
  `{"messaging_product":"whatsapp","to":"<id>","type":"text","text":{"body":"..."}}`.
  Flattening `text` to a top-level string is rejected by the API.
- **24-hour session window.** Outside a 24-hour window from the user's last
  message, only pre-approved template messages are deliverable (not exercised by
  the test suite, noted for production).
- **Rate limits** surface as Cloud API error code `80007` / HTTP `429`.

---

## How the tests exercise the trust boundary

The trust boundary is the whole point of the adapter — these tests prove the
agent only ever acts on authenticated, correctly-classified input:

- **Owner vs stranger** (`test_on_message_owner_returns_valid_envelope`,
  `test_on_message_stranger_is_untrusted`) — the same wire-format event yields
  `trust_level == owner_paired` when it comes from the paired owner and
  `untrusted` from an unknown sender. The adapter calls `classify()` *before*
  constructing the envelope, so the trust label can never be skipped.
- **Public allowlist** (`test_allowlist_silently_drops_stranger_in_public`) — in
  a public-channel context an unknown sender is dropped (no envelope), so
  strangers can't address the agent in shared spaces.
- **Signature verification** (`test_channel_specific_behaviour_signature_verification`)
  — unsigned and tampered webhooks return `None` and **no envelope is built**;
  only a correctly-signed body produces a `ChannelMessage`. Without this, anyone
  who discovers the webhook URL could inject messages — so this is where the
  adapter authenticates the channel itself, not just the sender.

Robustness around the boundary is covered too: forced disconnects return cleanly
(`test_disconnect_is_handled`) and rate-limits propagate as a structured 429
(`test_rate_limit_propagates_429`) rather than crashing.

---

## Running the tests

```sh
uv run pytest tests/channels/test_whatsapp.py -v
```

All seven pass:

```
7 passed
```

The mock-API fake at `tests/channels/mocks/whatsapp_mock.py` is the contract
surface (do not edit it or the test file — they are fixed).

---

## Known limitations

- Outbound HTTP to the real Graph API is stubbed (`send` returns the body when no
  mock is injected); wiring the real client is a production follow-up.
- Only text messages are handled; media/attachments and the 24-hour template flow
  are out of scope for this slot.
- The Twilio provider path is not implemented here — this adapter targets the Meta
  Cloud API, which is what the test suite is based on.
