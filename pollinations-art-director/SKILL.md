---
name: pollinations-art-director
description: Turn a topic into a finished illustrated and narrated storybook using Pollinations models. Use when someone asks for a picture story, storybook, bedtime story with illustrations, narrated slideshow, or any creative piece that combines generated text, images and audio into one shareable HTML page. The skill writes the story, draws consistent pages, records narration and assembles the book, spending from the user's own Pollinations balance.
license: MIT
compatibility: Requires Python 3.9+ (stdlib only) and network access to gen.pollinations.ai and enter.pollinations.ai.
metadata:
  author: benjaminkincses
  version: "1.0"
---

# Pollinations Art Director

Give it a topic, get back a finished storybook: a short story written for the
topic, one illustration per page drawn in a single consistent style with a
recurring character, a narrated MP3 of the full text, and a `storybook.html`
that puts it all together. Every generation call runs on Pollinations models
and spends from the user's own Pollinations balance.

## Before you start: sign-in

The scripts need the user's own Pollinations key. They look for it in this
order and stop at the first hit:

1. `POLLINATIONS_API_KEY` environment variable (key from
   https://enter.pollinations.ai/keys)
2. `~/.pollinations/credentials.json`, the file the polli CLI writes
3. A device flow sign-in: the script prints a verification URL, the user
   approves it in a browser, and the key is cached in
   `~/.pollinations/credentials.json`

If the user has no key yet, either run `npx @pollinations/cli auth login`
for them, or just run the script and let the device flow start. Never ask
the user to paste a key into chat, and never put a key in a file inside the
project. A 401 error means the key expired (device keys default to 7 days);
sign in again.

## Quick start

```bash
python3 scripts/make_storybook.py --topic "a lighthouse keeper's cat who guides ships home" --out ./the-lighthouse-cat
```

Output in the target folder:

- `storybook.html` - the finished book, open it in a browser
- `story.json` - the story brief (title, style, character, page texts)
- `page-1.jpg` ... `page-N.jpg` - the illustrations
- `narration.mp3` - the whole story read aloud
- `cover.jpg` - copy of the first illustration, handy as a preview image

The script prints a JSON summary with the title and file paths when it
finishes. Show the user the title and where `storybook.html` is.

## How it works

1. **Brief.** A text model returns JSON only: a title, one style sentence
   (medium, palette, mood), one character sentence (exact appearance), and
   per page a short story text plus a one-sentence scene description.
2. **Illustrations.** Each page image prompt is style sentence + character
   sentence + that page's scene, with seeds counting up from one base seed.
   Repeating the style and character text verbatim is what keeps the pages
   looking like one book.
3. **Narration.** The page texts are joined and sent to a speech model.
   Long stories are split on sentence boundaries and the MP3 parts are
   concatenated.
4. **Assembly.** Pages, texts and the audio player are filled into
   `assets/storybook_template.html`.

## Useful options

- `--pages N` - story length, default 4. Six or fewer keeps cost and
  runtime sane.
- `--seed N` - change it to redraw the same story with different art.
- `--voice NAME` - narration voice, default `alloy`.
- `--no-audio` - skip narration when the user only wants a picture book.
- Models are set in `scripts/polli_client.py` and can be overridden with
  the `POLLI_TEXT_MODEL`, `POLLI_IMAGE_MODEL`, `POLLI_TTS_MODEL` and
  `POLLI_TTS_VOICE` environment variables. See `references/api-notes.md`
  for endpoints, defaults and sign-in details.

## Driving the steps by hand

When the user wants changes, work on the pieces instead of rerunning
everything:

- **Rewrite the story:** edit `story.json`, then rerun only the steps that
  depend on the changed fields (texts feed narration, scenes feed images).
- **Redraw one page:** call `generate_image` from `scripts/polli_client.py`
  with the same style and character sentences and a new seed, and replace
  that page file.
- **Reuse the client elsewhere:** `polli_client.py` exposes `chat`,
  `generate_image` and `text_to_speech` and handles auth and retries, so
  small one-off generations (a poster, a jingle voiceover, a comic panel)
  can import it directly.

## Troubleshooting

- **401 Unauthorized:** key missing, expired or revoked. Sign in again with
  the polli CLI or let the device flow run.
- **Truncated downloads:** the client checks Content-Length and retries up
  to 4 times per call. If a call still fails, rerun the script; finished
  pages from a previous run can be kept by reusing the same output folder
  and story.
- **Brief is not valid JSON:** the script already retries once with a
  repair prompt. If it still fails, lower the page count or simplify the
  topic and run again.
- **Cost:** one run is 1 chat call, 1 image call per page and 1 to 2
  speech calls, all billed to the signed-in user's balance.
