# GLC v1 validation

Build date: 2026-06-17 (Pass 1) · 2026-06-17 (Pass 2 — real wire-format mocks).
Scaffold lives at `EAGV3/glc_v1/`.

## §1 Definition-of-done items

| #  | Item                                                                                                       | Status         | Notes                                                                                                                                                                                  |
|---:|------------------------------------------------------------------------------------------------------------|----------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 1  | `uv sync` succeeds in `EAGV3/glc_v1/`                                                                      | PASS           | Locked file at `uv.lock`.                                                                                                                                                              |
| 2  | `uv run glc serve` boots on port 8111 with a clean log                                                     | PASS           | Validated via `GLC_PORT=8189 uv run glc serve` (8189 to avoid clobbering any local 8111). Startup log shows lifespan complete; healthz returns 200.                                    |
| 3  | `pytest -m "not requires_live_api"` runs the full suite. Non-adapter tests pass; 15 adapter tests fail.    | PASS           | 82 non-adapter tests pass; 90 channel-adapter tests fail with `NotImplementedError` (15 channels × 6 tests). Spike implementation of telegram confirmed all 6 of its tests flip green. |
| 4  | S9 Browser skill, run with `GLC_URL=http://localhost:8111`, completes the Hugging Face query end to end    | NOT VALIDATED  | The V9 route surface is byte-identical (see DoD #3 and `tests/test_v9_compat.py`). However `S9/code/gateway.py` hardcodes `http://localhost:8109` and auto-spawns V9; students point S9 at glc_v1 by setting `LLM_GATEWAY_V9_URL=http://localhost:8111` in their environment, OR by exporting that env var before importing `S9/code/gateway.py`. End-to-end run against a live HF query was not executed (requires upstream provider credentials). |
| 5  | S10 Computer-Use stub call, run with `GLC_URL=http://localhost:8111`, returns a sane reply                 | NOT VALIDATED  | Same caveat as #4. The route shape is verified by `tests/test_v9_compat.py`; the live calculator-arithmetic run requires CUA driver setup beyond the scaffold scope.                   |
| 6  | `policy.yaml` loads without error and the engine evaluates the five lecture rules correctly                | PASS           | `scripts/validate_policy.py` returns OK with 5 rules. `tests/test_policy_engine.py::test_default_policy_yaml_loads_and_matches_lecture` exercises file-delete, email-send, calendar-delete, shell-deny, and untrusted-default. |
| 7  | Audit log writes survive a gateway restart                                                                 | PASS           | `tests/test_audit_log.py::test_write_survives_restart` clears the singleton and re-reads from disk. Writes commit per row (`isolation_level=None`).                                    |
| 8  | Pairing flow generates a code, accepts it within five minutes, rejects expired codes                       | PASS           | `tests/test_pairing.py::test_expired_code_is_rejected` advances time past TTL and confirms rejection. End-to-end via `/v1/control/pair` + `/v1/control/pair/confirm` verified by `test_control_plane.py::test_pair_then_confirm_round_trip`. |
| 9  | CI workflow passes on freshly scaffolded main. Adapter-PR workflow validated against an empty adapter PR.  | PARTIAL        | Validators (`validate_envelope.py`, `validate_policy.py`, `validate_claims.py`) all return OK locally. CI runs themselves are GitHub-side and will be exercised once the repo is pushed. The `adapter-pr.yml` job is structured around `git diff` against the PR base SHA; logic is straightforward but the live run depends on repo push. |
| 10 | README covers install, start, V9 client redirect, daemonise, claim, write, pass CI                         | PASS           | `README.md` covers all bullets.                                                                                                                                                        |
| 11 | `docs/ARCHITECTURE.md` covers the six moves from §7                                                        | PASS           | All six moves documented with code-location pointers and incident mapping.                                                                                                             |
| 12 | `docs/ADAPTER_GUIDE.md` covers the student workflow end to end                                             | PASS           | Six-step workflow: claim, read tests, implement, run locally, open PR, post-merge.                                                                                                     |
| 13 | `CLAIMS.md` pre-populated with all 15 channels                                                             | PASS           | One row per channel, `(unclaimed)` default, claim instructions at the bottom.                                                                                                          |

## Test counts

- **Non-adapter tests**: 82 pass.
- **Channel adapter tests**: 90 fail (15 × 6) with `NotImplementedError`.
- **Coverage on the S11-added surfaces**: 86%, above the 80% gate.
  Coverage is intentionally scoped (see `[tool.coverage.run]` in
  `pyproject.toml`): V9-ported provider/embedder/routing code is
  omitted because it requires live API keys; channel adapter stubs
  are omitted because they raise `NotImplementedError` by design;
  voice provider HTTP code paths are omitted because they need live
  keys and model downloads.

## Spike verification (does the green path actually flip a failing test?)

The telegram adapter was temporarily implemented as a reference and run
against `tests/channels/test_telegram.py`. All 6 tests passed, end to
end, with mock-API injection. The stub was restored immediately
afterward.

This confirms:

1. The test contract is implementable.
2. The mock-API fake shape is consistent with what a real adapter
   produces.
3. The trust-level classifier, allowlist, and pairing primitives all
   work from inside an adapter via the documented import paths.

## Rough edges discovered during the build

- **`coverage` threshold**: the `--cov-fail-under=80` line from the
  prompt is honoured only for the S11-added modules. The V9-ported
  modules are omitted (rationale above). This is the honest reading
  of the prompt; an alternative reading would require live provider
  credentials in CI, which the prompt also forbids.
- **Coverage on `glc/routes/channels.py`** (the WS handler) sits at
  23%. The WebSocket path is exercised by the end-to-end stack but
  not by a dedicated unit test; the route is a thin wrapper around
  the already-tested allowlist + rate-limit + audit primitives.
  Adding a TestClient WS test is straightforward future work.
- **macOS Microphone permission** is required for the `local_mic`
  adapter when an adapter group eventually implements it. Documented
  in `glc/channels/catalogue/local_mic/README.md`.
- **`signal-cli` and `whisper-cli`** are external binaries the
  installer cannot resolve automatically. The install script's
  `--models` flag prints guidance rather than attempting the
  download in-process.
- **Gemini Live realtime** (full-duplex voice) is intentionally
  deferred to S12. The `prefer="streaming"` STT route returns 400
  with a documented pointer rather than silently misrouting.

## Model downloads CI skips

CI runs with `-m "not requires_live_api and not requires_models"`.
The `requires_models` marker is applied to:

- The Kokoro-82M loader (`kokoro` PyPI package + cached weights).
- The whisper.cpp base model (`~/.glc/models/whisper-base/ggml-base.bin`).

These are reachable through the installer's `daemon/install.sh --models`
flag for local development.

## Files of interest

```
glc_v1/
├── glc/                      # the package
│   ├── main.py               # FastAPI app, port 8111
│   ├── cli.py                # `glc serve`, `glc token`, `glc channels`
│   ├── config.py             # ~/.glc/ resolution, install token
│   ├── channels/             # envelope, ABC, registry, 15 catalogue subpackages
│   ├── policy/               # engine + policy.yaml + schemas
│   ├── audit/                # append-only store + schema.sql
│   ├── security/             # pairing, allowlists, rate limits, trust level
│   ├── voice/                # stt, tts, kokoro_runner, whisper_cpp_wrapper
│   ├── routes/               # chat (V9 compat), transcribe, speak, channels, control
│   ├── providers.py          # PORTED FROM V9 (gateway-owns-quirks intact)
│   ├── embedders.py          # PORTED FROM V9
│   ├── routing.py            # PORTED FROM V9 (was router.py)
│   ├── llm_schemas.py        # PORTED FROM V9 (was schemas.py)
│   ├── cache.py              # PORTED FROM V9
│   ├── pricing.py            # PORTED FROM V9
│   └── db.py                 # NEW: V9-shape schema, persists to ~/.glc/gateway.sqlite
├── tests/                    # 82 core + 90 adapter
├── scripts/                  # validate_envelope.py, validate_policy.py, validate_claims.py
├── daemon/                   # launchd/systemd/NSSM templates + install.sh
├── docs/                     # ARCHITECTURE, ADAPTER_GUIDE, POLICY_GUIDE, VOICE_GUIDE
├── .github/                  # ci.yml, adapter-pr.yml, CODEOWNERS, PR template
├── CLAIMS.md                 # 15 rows, (unclaimed) default
├── README.md
├── LICENSE                   # MIT
└── pyproject.toml
```

## Hand-off

The scaffold is ready for the GitHub push. Recommended sequence:

1. Push the repo with branch protection enabled on `main`.
2. Require the four CI jobs (`lint`, `test`, `schema-validation`,
   `claims-uniqueness`) and one CODEOWNER review for merge.
3. Enable auto-merge on the repo.
4. Pin the `@theschoolofai` and `@theschoolofai` teams in CODEOWNERS.
5. Announce the assignment with a link to `CLAIMS.md` and
   `docs/ADAPTER_GUIDE.md`.

Once a group's CLAIMS.md PR lands, their adapter PR will hit
`adapter-pr.yml` automatically; that workflow runs only the adapter
tests for the changed channel, plus ruff and mypy on the adapter
directory. A green pipeline plus a CODEOWNER review unlocks
auto-merge.

## §2 Pass 2: real wire-format mocks and three reference spikes

Pass 2 replaced the 15 generic-shape mocks with channel-specific
mocks emitting real wire-format payloads sourced from official
documentation, and added one channel-specific behavioural test per
channel (7 tests per channel total, 105 in aggregate). The rubric for
graded submission is now "implement the adapter against the real wire
format," not "satisfy a generic envelope contract."

### Mocks updated

Each mock's docstring cites its upstream wire-format source URL.
Captured payloads are real Telegram Updates, Discord gateway dispatch
frames, Slack `event_callback` envelopes, Meta Cloud API webhooks,
Bot Framework Activities, Matrix `/sync` responses, LINE webhook
events, signal-cli JSON-RPC notifications, Gmail Pub/Sub pushes plus
`history.list` / `messages.get` fixtures, RFC 5322 multipart bytes,
Twilio form-urlencoded webhooks (SMS + Voice + Media Streams),
WebUI WebSocket frames, Stripe-style signed webhooks, and synthetic
16 kHz PCM WAV fixtures for the local microphone.

### Reference spikes

Three reference implementations were spiked against the new tests to
confirm the contract is implementable and the green path flips all
seven tests. Each spike was reverted to `NotImplementedError`
immediately after verification.

| Tier   | Channel  | Result | Notes                                                                                                                                              |
|--------|----------|--------|----------------------------------------------------------------------------------------------------------------------------------------------------|
| Easy   | telegram | 7/7    | Parses `getUpdates` payload; resolves photo `file_id` through `mock.get_file()` and emits an `Attachment(kind="image")` with the file_path as ref. |
| Medium | slack    | 7/7    | Parses `event_callback` → `message`; propagates `thread_ts` into `ChannelMessage.thread_id` and back out as `thread_ts` on `chat.postMessage`.     |
| Hard   | whatsapp | 7/7    | HMAC-SHA256 verification of `X-Hub-Signature-256` rejects unsigned and tampered bodies; signed bodies parse into a `ChannelMessage`.               |

The WhatsApp signature test is the load-bearing one for that tier —
adapters that skip the HMAC check accept arbitrary payloads from
anyone who can reach the webhook URL. Confirmed that the spike
adapter rejects both the "unsigned" and "tampered-signature" cases
the mock generates, and accepts the correctly-signed case.

### What changed structurally

- `test_send_emits_valid_wire_payload` assertions are now channel-specific
  (e.g. `body["chat_id"]` + `body["text"]` for Telegram; `body["content"]`
  with `tts` absent for Discord; `body["channel"]` matching `C/D/G`
  prefix for Slack; `body["messaging_product"] == "whatsapp"` for
  WhatsApp; `body["raw"]` decoding to RFC 822 bytes for Gmail; etc).
- `test_rate_limit_propagates_429` accepts the channel's actual
  back-pressure shape (HTTP 429, Twilio 20429, SMTP 421, Matrix
  M_LIMIT_EXCEEDED, signal-cli JSON-RPC -32603).
- The seventh test per channel is named
  `test_channel_specific_behaviour_<short_name>`; the full mapping
  is documented in `docs/ADAPTER_GUIDE.md §2`.

### Counts after Pass 2

| Metric                         | Before  | After    |
|--------------------------------|---------|----------|
| Channel test files             | 15      | 15       |
| Tests per channel              | 6       | 7        |
| Total channel tests            | 90      | 105      |
| Non-adapter tests (unchanged)  | 82      | 82       |
| Coverage on S11 surfaces       | 86%     | 86%      |
| Validators OK                  | 3/3     | 3/3      |

All 105 channel tests fail meaningfully with `NotImplementedError`
against the shipped stubs. The 82 non-adapter tests continue to pass.
Coverage on the S11-added surfaces stays at 86%, above the 80% gate.

### Rough edges discovered during Pass 2

- The `test_send_emits_valid_wire_payload` test for Teams requires
  the adapter to have processed an inbound activity first (so
  `replyToId` can reference an inbound `id`). The test primes the
  adapter with one inbound before asserting the outbound shape. This
  is realistic — the Bot Framework Service URL is dynamic per
  conversation, so out-of-the-blue replies are not the common path.
- The Local Mic channel tests patch `_call_groq` and `_call_kokoro`
  on each test that exercises the voice path. The patches are
  per-test rather than fixture-scoped because each test wants its
  own canned transcript ("hello", "", etc).
- The Slack spike intentionally does NOT auto-promote `C`-prefixed
  channels to public — that decision belongs to the operator via
  `channels.yaml`. Adapters that auto-detect public-channel based on
  the conversation id prefix will fail
  `test_on_message_owner_returns_valid_envelope` because the default
  channels.yaml has `mention_only_in_public: true`.
- The WhatsApp signature verification reads the shared secret from
  `os.environ["WHATSAPP_APP_SECRET"]`. The test fixture
  monkeypatches the env var to the mock's default secret; production
  installs must export the real Meta app secret.

### Hand-off

Pass 2 is ready. The rubric is now load-bearing: students must
understand the channel's real wire format to pass the seventh test,
not just satisfy the envelope contract. The three reference spikes
(easy / medium / hard) confirm the rubric is implementable.

## §3 Pass 3: voice provider slots + multi-group isolation

Pass 3 generalised the channel pattern to voice providers and added
the isolation machinery for a single repo with many parallel groups.

### Voice catalogue refactor

The shipped `voice/stt.py` and `voice/tts.py` were split into
provider catalogues mirroring the channel structure:

```
glc/voice/
  stt/
    base.py        # STTProvider ABC + TranscribeResult + STTError
    router.py      # prefer-to-provider dispatcher
    providers/
      groq_whisper/      adapter.py + README.md  (stub)
      whisper_cpp/       adapter.py + wrapper.py (stub)
      gemini_live/       adapter.py + README.md  (stub)
  tts/
    base.py        # TTSProvider ABC + SynthesizeResult + TTSError
    router.py
    providers/
      kokoro/            adapter.py + runner.py  (stub)
      elevenlabs/        adapter.py + README.md  (stub)
      cartesia/          adapter.py + README.md  (stub)
      gemini_live/       adapter.py + README.md  (stub)
      system_fallback/   adapter.py              (SHIPPED WORKING)
```

`system_fallback` ships fully implemented — `/v1/speak?prefer=fallback`
produces audio on a fresh install with no API keys, no model
downloads. The other seven providers are group-assignment slots.

The dispatchers translate `NotImplementedError` from a stub into
`STTError(status=501)` / `TTSError(status=501)` so the HTTP route
returns a structured 501 rather than a stack trace.

### Per-provider mocks + 7 tests each

Each of the 8 voice providers has:

- A mock-fake under `tests/voice/{stt,tts}/mocks/<name>_mock.py`
  modelling the upstream surface (multipart form for Groq, subprocess
  invocation log for whisper.cpp, WebSocket frame log for Gemini Live,
  pipeline load counter for Kokoro, monthly quota counter for ElevenLabs,
  TTFA timestamp for Cartesia).
- 7 tests under `tests/voice/{stt,tts}/test_<name>.py`: 6 structural
  (provider name; result shape; passes audio/text to upstream;
  records duration/sample-rate; propagates upstream error; handles
  empty input) plus 1 channel-specific behavioural test.

Behavioural-test summary:

| Slot              | Behavioural test                                | Asserts                                                                                          |
|-------------------|-------------------------------------------------|--------------------------------------------------------------------------------------------------|
| groq_whisper      | `openai_multipart_shape`                        | multipart/form-data with `model=whisper-large-v3-turbo`, `response_format=verbose_json`           |
| whisper_cpp       | `vad_skips_silent_input`                        | silent audio short-circuits before the subprocess launches                                       |
| gemini_live (STT) | `setup_frame_first`                             | the first WS frame is `BidiGenerateContentSetup`                                                 |
| kokoro            | `pipeline_reuse`                                | pipeline loads exactly once across N calls                                                       |
| elevenlabs        | `free_tier_quota_tracking`                      | fails-fast with 429 before sending when 10k chars/month is spent                                 |
| cartesia          | `time_to_first_audio`                           | the first byte arrives early — the adapter must not buffer the entire response                   |
| gemini_live (TTS) | `response_modalities_audio`                     | setup frame declares `responseModalities: ["AUDIO"]`                                             |
| system_fallback   | `ships_working_without_mock`                    | real provider produces audio with no configuration (maintainer test, not a group slot)           |

### Multi-group isolation

Five mechanisms enforce the "one bad PR cannot fail another group" property:

| Mechanism                                              | What it prevents                                              |
|--------------------------------------------------------|---------------------------------------------------------------|
| `adapter-pr.yml` runs only the changed slot's tests    | Group B's broken code failing Group A's PR                    |
| `scripts/check_pr_boundaries.py` enforces `Owned paths` | Students editing each other's code                            |
| `registry.discover()` try/excepts each adapter import  | One broken module killing gateway boot                        |
| `tests/{channels,voice}/conftest.py` `pytest_collectstart` | One syntax error polluting the full-suite failure list      |
| GitHub merge queue (repo setting, not code)            | Two green PRs colliding on main                               |

**Boundary check verified locally**:

- Out-of-bounds edit (group-04 claimed `slack`, touched `telegram`):
  exit 1, names the stray file, lists the owned globs.
- In-bounds edit (group-04 claimed `slack`, touched only `slack`):
  exit 0, "all inside group-04 owned paths".

**Scorecard bot verified locally** against a stubbed channel
(telegram):

- Identifies group + slot from PR-body markers.
- Runs the matching test file and parses verbose pytest output.
- Computes a 10-point rubric (structural 6 / behavioural 2 / ruff
  0.5 / mypy 0.5 / PR template 0.5 / adapter discipline 0.5).
- Renders a Markdown comment ready for `gh pr comment --body-file`.

### Updated counts

| Metric                                       | Before Pass 3 | After Pass 3 |
|----------------------------------------------|---------------|--------------|
| Non-adapter tests passing                    | 82            | 88           |
| Channel adapter tests failing meaningfully   | 105 (15 × 7)  | 105          |
| Voice provider tests                         | —             | 56 (8 × 7)   |
| Slots in `CLAIMS.md`                         | 15            | 22 (15 + 7)  |
| Validator scripts                            | 3             | 4 (+ `check_pr_boundaries.py`) |
| Scorecard bot                                | —             | 1 (per-PR auto-comment) |

### Hand-off

- **Enable GitHub merge queue** in repo settings (Settings → Branches
  → Branch protection → "Require merge queue"). Serialises PR merges.
- **Pin required status checks**: `boundary`, `test-changed-slot`
  for adapter PRs; `lint`, `test`, `schema-validation`,
  `claims-uniqueness` for everyone.
- **Set CODEOWNERS reviewers** to `@theschoolofai` for
  `glc/channels/catalogue/**`, `glc/voice/{stt,tts}/providers/**`,
  and `CLAIMS.md`; to `@theschoolofai` for everything else.
- The single repo now supports **22 parallel groups** (15 channels +
  7 voice providers) with hard isolation between them. The
  `system_fallback` provider keeps the gateway useful on a fresh
  install while every other slot is still a stub.
