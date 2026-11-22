#!/usr/bin/env python3
"""Build an illustrated, narrated storybook from a topic.

Pipeline:
  1. A text model writes a story brief as JSON (title, shared style block,
     one recurring character, one short text + scene per page).
  2. An image model draws every page with the same style block, character
     description and a fixed seed base, so the pages look like one book.
  3. A speech model narrates the full story text into narration.mp3.
  4. The pages, texts and audio are assembled into storybook.html.

Usage:
  python3 make_storybook.py --topic "a lighthouse keeper's cat" --out ./out
  python3 make_storybook.py --topic "a robot learning to bake" --pages 6 --no-audio

Auth and models: see polli_client.py. Everything spends from the caller's
own Pollinations balance.
"""

import argparse
import json
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import polli_client as pc

BRIEF_SYSTEM = (
    "You write short illustrated storybooks. Answer with JSON only, no code "
    "fences, no commentary. Schema: "
    '{"title": str, "style": str, "character": str, '
    '"pages": [{"text": str, "scene": str}]}. '
    '"style" is one sentence describing the illustration style, medium, '
    "palette and mood, reused verbatim for every page. \"character\" is one "
    "sentence describing the main character's exact appearance, reused "
    'verbatim for every page. Each page "text" is 1 to 2 short sentences of '
    'story prose. Each page "scene" is one sentence describing what the '
    "illustration for that page shows. The story has a clear beginning, a "
    "middle and an end."
)


def get_brief(topic, pages):
    user = "Topic: %s\nPages: %d" % (topic, pages)
    raw = pc.chat(
        [
            {"role": "system", "content": BRIEF_SYSTEM},
            {"role": "user", "content": user},
        ],
        temperature=0.8,
    )
    text = raw.strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
    try:
        brief = json.loads(text)
    except ValueError:
        fixed = pc.chat(
            [
                {"role": "system", "content": "Fix the following into valid JSON matching the storybook schema. JSON only."},
                {"role": "user", "content": text},
            ],
            temperature=0.2,
        )
        brief = json.loads(re.sub(r"^```(?:json)?|```$", "", fixed.strip(), flags=re.MULTILINE).strip())
    if not brief.get("pages"):
        raise RuntimeError("Brief came back with no pages: " + str(brief)[:300])
    return brief


def main():
    ap = argparse.ArgumentParser(description="Make an illustrated, narrated storybook with Pollinations.")
    ap.add_argument("--topic", required=True, help="What the story is about.")
    ap.add_argument("--pages", type=int, default=4, help="Number of pages (default 4).")
    ap.add_argument("--out", default="./storybook-out", help="Output directory.")
    ap.add_argument("--seed", type=int, default=42, help="Base seed for the images (default 42).")
    ap.add_argument("--voice", default=None, help="Narration voice (default from polli_client).")
    ap.add_argument("--no-audio", action="store_true", help="Skip narration.")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)

    print("1/4 Writing the story brief...", file=sys.stderr)
    brief = get_brief(args.topic, args.pages)
    with open(os.path.join(args.out, "story.json"), "w") as f:
        json.dump(brief, f, indent=2, ensure_ascii=False)
    print("    Title: " + brief["title"], file=sys.stderr)

    print("2/4 Illustrating %d pages..." % len(brief["pages"]), file=sys.stderr)
    page_files = []
    for i, page in enumerate(brief["pages"], start=1):
        prompt = "%s Main character: %s Scene: %s" % (brief["style"], brief["character"], page["scene"])
        raw = pc.generate_image(prompt, seed=args.seed + i)
        name = "page-%d%s" % (i, pc.image_extension(raw))
        with open(os.path.join(args.out, name), "wb") as f:
            f.write(raw)
        page_files.append(name)
        print("    " + name, file=sys.stderr)

    narration_name = None
    if not args.no_audio:
        print("3/4 Recording narration...", file=sys.stderr)
        full_text = " ".join(p["text"] for p in brief["pages"])
        # TTS calls stay short; split on sentence boundaries if needed.
        chunks = [full_text] if len(full_text) <= 700 else re.findall(r"[^.!?]+[.!?]+", full_text)
        audio = b"".join(pc.text_to_speech(c.strip(), voice=args.voice) for c in chunks if c.strip())
        narration_name = "narration.mp3"
        with open(os.path.join(args.out, narration_name), "wb") as f:
            f.write(audio)
        print("    narration.mp3 (%d bytes)" % len(audio), file=sys.stderr)
    else:
        print("3/4 Skipping narration (--no-audio).", file=sys.stderr)

    print("4/4 Assembling storybook.html...", file=sys.stderr)
    template_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "assets", "storybook_template.html"
    )
    with open(template_path) as f:
        template = f.read()
    sections = []
    for name, page in zip(page_files, brief["pages"]):
        sections.append(
            '<section class="page"><img src="%s" alt="">'
            "<p>%s</p></section>" % (name, _esc(page["text"]))
        )
    audio_html = ""
    if narration_name:
        audio_html = '<div class="player"><audio controls src="%s"></audio></div>' % narration_name
    html = (
        template.replace("{{TITLE}}", _esc(brief["title"]))
        .replace("{{AUDIO}}", audio_html)
        .replace("{{PAGES}}", "\n".join(sections))
    )
    out_html = os.path.join(args.out, "storybook.html")
    with open(out_html, "w") as f:
        f.write(html)
    shutil.copyfile(
        os.path.join(args.out, page_files[0]), os.path.join(args.out, "cover" + os.path.splitext(page_files[0])[1])
    )
    print(json.dumps({"title": brief["title"], "out": os.path.abspath(args.out),
                      "pages": page_files, "narration": narration_name,
                      "html": os.path.abspath(out_html)}, indent=2))


def _esc(text):
    return (
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )


if __name__ == "__main__":
    main()
