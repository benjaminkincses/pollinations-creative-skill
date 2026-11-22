# Pollinations API notes for this skill

Base URL for generation: `https://gen.pollinations.ai`
Auth on every call: `Authorization: Bearer <key>`, where the key is the
caller's own Pollinations key (`sk_...`). Never hardcode a key.

Full model list: `GET https://gen.pollinations.ai/v1/models`

## Endpoints used

### Chat (story brief)
`POST /v1/chat/completions`
Body: `{"model": "openai/gpt-5.4-nano", "messages": [...], "temperature": 0.8}`
Reply: OpenAI shape, text at `choices[0].message.content`.

### Images (page illustrations)
`POST /v1/images/generations`
Body: `{"model": "black-forest-labs/flux.1-schnell", "prompt": "...", "size": "1024x1024", "seed": 43}`
Reply: JSON with `data[0].b64_json`, or a raw image body. Passing the same
style sentence, the same character sentence and nearby seeds keeps a set of
pages visually consistent.

### Speech (narration)
`POST /v1/audio/speech`
Body: `{"model": "openai/tts-1", "input": "...", "voice": "alloy"}`
Reply: raw MP3 bytes (`audio/mpeg`). Keep each call under roughly 700
characters; concatenate the MP3 bytes for longer stories.

## Default models

Set in `scripts/polli_client.py`, each overridable by environment variable:

| Purpose | Env var | Default |
| --- | --- | --- |
| Text | `POLLI_TEXT_MODEL` | `openai/gpt-5.4-nano` |
| Image | `POLLI_IMAGE_MODEL` | `black-forest-labs/flux.1-schnell` |
| Speech | `POLLI_TTS_MODEL` | `openai/tts-1` |
| Voice | `POLLI_TTS_VOICE` | `alloy` |

## Sign-in options (caller's own account)

1. `POLLINATIONS_API_KEY` env var, key from https://enter.pollinations.ai/keys
2. `npx @pollinations/cli auth login` (the polli CLI), which stores the key
   in `~/.pollinations/credentials.json`; the client reads that file.
3. The device flow built into `polli_client.py`: it requests a code at
   `POST https://enter.pollinations.ai/api/device/code`, prints a
   verification URL for the user to approve, polls
   `POST https://enter.pollinations.ai/api/device/token`, and caches the
   returned `sk_...` key in `~/.pollinations/credentials.json` (mode 0600).

Background: the Pollinations Pay / BYOP doc in the pollinations repo
(`BRING_YOUR_OWN_POLLEN.md`) describes the device flow and key types.

## Gotchas

- Large image and audio responses can arrive truncated behind some
  proxies. The client compares the body length with Content-Length and
  retries up to 4 times; the later attempts fall back to the `curl` binary
  when one is installed, which survives proxies that cut Python streams.
- A 401 means the key is missing, expired or revoked. Device-flow keys
  default to a 7 day lifetime; sign in again to renew.
- Every call spends from the signed-in account's Pollen balance. A 4 page
  storybook costs one chat call, 4 image calls and 1 or 2 speech calls.
