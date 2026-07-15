# Group assignments

The 22 GLC v1 groups are listed below with the slot each one owns. Group
assignments are **fixed by the instructors** — there is no claim PR, no
first-come-first-served, no swap. If you think the assignment is wrong,
post in the S11 chat (the group's `G<n>` sub-channel) and a TA will sort
it out.

Each row's **Owned paths** column lists the directories the assigned
group may touch. The boundary CI check
([`scripts/check_pr_boundaries.py`](scripts/check_pr_boundaries.py))
rejects PRs whose diff strays outside the owned paths. If a slot needs
a shared-code change, open a separate PR scoped to that change under
`@theschoolofai` review.

## Chat sub-channel numbering

Group chat sub-channels in the Axiom panel are labelled `G1 … G22` in
alphabetical order of group name:

- `G1` — Group Cartesia
- `G2` — Group Discord
- `G3` — Group ElevenLabs
- `G4` — Group Gemini Live STT
- `G5` — Group Gemini Live TTS
- `G6` — Group Gmail
- `G7` — Group Groq Whisper
- `G8` — Group IMAP
- `G9` — Group Kokoro
- `G10` — Group LINE
- `G11` — Group Local Mic
- `G12` — Group Matrix
- `G13` — Group Signal
- `G14` — Group Slack
- `G15` — Group Teams
- `G16` — Group Telegram
- `G17` — Group Twilio SMS
- `G18` — Group Twilio Voice
- `G19` — Group Webhook
- `G20` — Group WebUI
- `G21` — Group WhatsApp
- `G22` — Group Whisper.cpp

## Channels (15)

| Slot           | Group               | Owned paths                                                                          |
|----------------|---------------------|--------------------------------------------------------------------------------------|
| discord        | Group Discord       | `glc/channels/catalogue/discord/` `glc/channels/catalogue/discord/**`                 |
| gmail          | Group Gmail         | `glc/channels/catalogue/gmail/` `glc/channels/catalogue/gmail/**`                     |
| imap           | Group IMAP          | `glc/channels/catalogue/imap/` `glc/channels/catalogue/imap/**`                       |
| line           | Group LINE          | `glc/channels/catalogue/line/` `glc/channels/catalogue/line/**`                       |
| local_mic      | Group Local Mic     | `glc/channels/catalogue/local_mic/` `glc/channels/catalogue/local_mic/**`             |
| matrix         | Group Matrix        | `glc/channels/catalogue/matrix/` `glc/channels/catalogue/matrix/**`                   |
| signal         | Group Signal        | `glc/channels/catalogue/signal/` `glc/channels/catalogue/signal/**`                   |
| slack          | Group Slack         | `glc/channels/catalogue/slack/` `glc/channels/catalogue/slack/**`                     |
| teams          | Group Teams         | `glc/channels/catalogue/teams/` `glc/channels/catalogue/teams/**`                     |
| telegram       | Group Telegram      | `glc/channels/catalogue/telegram/` `glc/channels/catalogue/telegram/**`               |
| twilio_sms     | Group Twilio SMS    | `glc/channels/catalogue/twilio_sms/` `glc/channels/catalogue/twilio_sms/**`           |
| twilio_voice   | Group Twilio Voice  | `glc/channels/catalogue/twilio_voice/` `glc/channels/catalogue/twilio_voice/**`       |
| webhook        | Group Webhook       | `glc/channels/catalogue/webhook/` `glc/channels/catalogue/webhook/**`                 |
| webui          | Group WebUI         | `glc/channels/catalogue/webui/` `glc/channels/catalogue/webui/**`                     |
| whatsapp       | Group WhatsApp      | `glc/channels/catalogue/whatsapp/` `glc/channels/catalogue/whatsapp/**`               |

## Voice providers — STT (3)

| Slot             | Group                  | Owned paths                                                                       |
|------------------|------------------------|-----------------------------------------------------------------------------------|
| gemini_live_stt  | Group Gemini Live STT  | `glc/voice/stt/providers/gemini_live/` `glc/voice/stt/providers/gemini_live/**`    |
| groq_whisper     | Group Groq Whisper     | `glc/voice/stt/providers/groq_whisper/` `glc/voice/stt/providers/groq_whisper/**`  |
| whisper_cpp      | Group Whisper.cpp      | `glc/voice/stt/providers/whisper_cpp/` `glc/voice/stt/providers/whisper_cpp/**`    |

## Voice providers — TTS (4)

| Slot             | Group                  | Owned paths                                                                       |
|------------------|------------------------|-----------------------------------------------------------------------------------|
| cartesia         | Group Cartesia         | `glc/voice/tts/providers/cartesia/` `glc/voice/tts/providers/cartesia/**`          |
| elevenlabs       | Group ElevenLabs       | `glc/voice/tts/providers/elevenlabs/` `glc/voice/tts/providers/elevenlabs/**`      |
| gemini_live_tts  | Group Gemini Live TTS  | `glc/voice/tts/providers/gemini_live/` `glc/voice/tts/providers/gemini_live/**`    |
| kokoro           | Group Kokoro           | `glc/voice/tts/providers/kokoro/` `glc/voice/tts/providers/kokoro/**`              |

`system_fallback` is **not** a group slot — it ships fully implemented
under the maintainers.

## How the boundary check reads this file

`scripts/check_pr_boundaries.py` parses each table row, extracts the
slot name, the assigned group, and the owned-path glob list. When a
PR is opened, the script runs `git diff` against the merge base and
fails if any changed file lies outside the owned paths of the slot
that group owns. The PR author identifies their group via a
`# Group: <name>` marker required in the PR description.

## Shared-code path

Changes outside any slot's owned paths require:

- A separate PR scoped only to the shared code.
- `@theschoolofai` review.
- Branch-protection bypass for the boundary check (the check passes
  trivially because the PR has no group marker).
