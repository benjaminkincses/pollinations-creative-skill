# pollinations-creative-skill

An agent skill that turns a topic into a finished storybook: story text,
consistent illustrations and voice narration, all generated with
Pollinations models and assembled into one HTML page.

The skill itself lives in [`pollinations-art-director/`](pollinations-art-director/SKILL.md)
and follows the [Agent Skills](https://agentskills.io) format, so it works
with any skills-compatible coding agent.

## What it makes

Topic in, storybook out:

- a short story written for the topic
- one illustration per page, same style and same main character throughout
- an MP3 narration of the full story
- a `storybook.html` that combines art, text and audio

Example output: [`examples/the-lighthouse-cat/`](examples/the-lighthouse-cat/)
(storybook page, page images, narration, and the story brief as JSON).

## Install

Copy the `pollinations-art-director/` folder into your agent's skills
directory, for example:

```bash
cp -r pollinations-art-director ~/.claude/skills/
```

The exact folder differs per agent client; any directory the client scans
for skills works.

## Sign-in

The skill spends from your own Pollinations balance, using your own key.
Three ways, checked in this order:

1. Set `POLLINATIONS_API_KEY` (get a key at https://enter.pollinations.ai/keys)
2. Run `npx @pollinations/cli auth login` once; the skill reads the stored
   credentials
3. Do nothing: on first run the skill starts a device sign-in, prints a
   link, and continues after you approve it

No key is ever hardcoded or stored inside the project.

## Usage

```bash
cd pollinations-art-director
python3 scripts/make_storybook.py --topic "a lighthouse keeper's cat who guides ships home" --out ./the-lighthouse-cat
```

Options: `--pages N` (default 4), `--seed N`, `--voice NAME`,
`--no-audio`. Models can be swapped with the `POLLI_TEXT_MODEL`,
`POLLI_IMAGE_MODEL`, `POLLI_TTS_MODEL` and `POLLI_TTS_VOICE` environment
variables. Details on endpoints and defaults:
[`pollinations-art-director/references/api-notes.md`](pollinations-art-director/references/api-notes.md).

Requires Python 3.9+, standard library only.

## Layout

```
pollinations-art-director/
  SKILL.md            skill metadata and instructions
  scripts/            polli_client.py (auth + API), make_storybook.py (pipeline)
  references/         API notes
  assets/             storybook HTML template
examples/
  the-lighthouse-cat/ one full generated storybook
```

## License

MIT
