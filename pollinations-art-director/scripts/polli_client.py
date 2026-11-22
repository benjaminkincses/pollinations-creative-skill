#!/usr/bin/env python3
"""Minimal Pollinations client for the art-director skill.

Stdlib only. Every call spends from the caller's own Pollinations balance.
The key is resolved in this order:

1. POLLINATIONS_API_KEY environment variable
2. ~/.pollinations/credentials.json (where `polli auth login` stores it)
3. The BYOP device flow (opens an approval page, polls for the key,
   then caches it in ~/.pollinations/credentials.json)

Large responses on this API occasionally arrive truncated, so downloads
retry until the byte count matches Content-Length.
"""

import base64
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

GEN_BASE = "https://gen.pollinations.ai"
ENTER_BASE = "https://enter.pollinations.ai"

TEXT_MODEL = os.environ.get("POLLI_TEXT_MODEL", "openai/gpt-5.4-nano")
IMAGE_MODEL = os.environ.get("POLLI_IMAGE_MODEL", "black-forest-labs/flux.1-schnell")
TTS_MODEL = os.environ.get("POLLI_TTS_MODEL", "openai/tts-1")
TTS_VOICE = os.environ.get("POLLI_TTS_VOICE", "alloy")

CRED_PATH = os.path.expanduser("~/.pollinations/credentials.json")


def _save_key(key):
    os.makedirs(os.path.dirname(CRED_PATH), exist_ok=True)
    with open(CRED_PATH, "w") as f:
        json.dump({"apiKey": key}, f)
    os.chmod(CRED_PATH, 0o600)


def _device_flow_login():
    """Run the BYOP device flow from BRING_YOUR_OWN_POLLEN.md."""
    payload = {}
    app_key = os.environ.get("POLLINATIONS_APP_KEY")
    if app_key:
        payload["client_id"] = app_key
    req = urllib.request.Request(
        ENTER_BASE + "/api/device/code",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode())
    print("To sign in with your Pollinations account, open:", file=sys.stderr)
    print("  " + data["verification_uri_complete"], file=sys.stderr)
    print("  Code: " + data["user_code"], file=sys.stderr)
    deadline = time.time() + data.get("expires_in", 1800)
    interval = data.get("interval", 5)
    while time.time() < deadline:
        time.sleep(interval)
        req = urllib.request.Request(
            ENTER_BASE + "/api/device/token",
            data=json.dumps({"device_code": data["device_code"]}).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                token = json.loads(resp.read().decode())
            key = token["access_token"]
            _save_key(key)
            print("Signed in. Key cached in " + CRED_PATH, file=sys.stderr)
            return key
        except urllib.error.HTTPError as e:
            body = json.loads(e.read().decode() or "{}")
            if body.get("error") == "authorization_pending":
                continue
            raise RuntimeError("Device flow failed: " + str(body))
    raise RuntimeError("Device flow timed out before approval.")


def get_api_key():
    key = os.environ.get("POLLINATIONS_API_KEY")
    if key:
        return key.strip()
    if os.path.exists(CRED_PATH):
        try:
            with open(CRED_PATH) as f:
                key = json.load(f).get("apiKey")
            if key:
                return key
        except (ValueError, OSError):
            pass
    return _device_flow_login()


_API_KEY = None


def _auth_key():
    global _API_KEY
    if _API_KEY is None:
        _API_KEY = get_api_key()
    return _API_KEY


class _Retryable(Exception):
    pass


def _check_complete(expected, raw):
    if expected is not None and len(raw) != int(expected):
        raise _Retryable("truncated response: got %d of %s bytes" % (len(raw), expected))


def _post_urllib(url, payload, timeout):
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": "Bearer " + _auth_key(),
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            ctype = resp.headers.get("Content-Type", "")
            expected = resp.headers.get("Content-Length")
            chunks = []
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                chunks.append(chunk)
            raw = b"".join(chunks)
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:400]
        if e.code == 401:
            raise RuntimeError(
                "Pollinations rejected the API key (401). Get a key at "
                "https://enter.pollinations.ai/keys or run: "
                "npx @pollinations/cli auth login\n" + detail
            )
        raise _Retryable("HTTP %d: %s" % (e.code, detail))
    except (IOError, OSError) as e:
        raise _Retryable(str(e))
    _check_complete(expected, raw)
    return ctype, raw


def _post_curl(url, payload, timeout):
    """Same POST via the curl binary. Some proxies cut long urllib streams
    short; curl gets the full body there. The key travels in a 0600 config
    file, never on the command line."""
    tmp = tempfile.mkdtemp(prefix="pollicurl-")
    try:
        cfg = os.path.join(tmp, "cfg")
        hdr = os.path.join(tmp, "hdr")
        with open(cfg, "w") as f:
            f.write('header = "Authorization: Bearer %s"\n' % _auth_key())
            f.write('header = "Content-Type: application/json"\n')
        os.chmod(cfg, 0o600)
        proc = subprocess.run(
            ["curl", "-sS", "--max-time", str(timeout), "-K", cfg,
             "-D", hdr, "-w", "%{http_code}", "--data-binary", "@-", url],
            input=json.dumps(payload).encode(),
            capture_output=True, timeout=timeout + 30,
        )
        if proc.returncode != 0:
            raise _Retryable("curl failed: " + proc.stderr.decode(errors="replace")[:200])
        status = int(proc.stdout[-3:])
        raw = proc.stdout[:-3]
        ctype, expected = "", None
        with open(hdr, "rb") as f:
            for line in f.read().decode(errors="replace").splitlines():
                low = line.lower()
                if low.startswith("content-type:"):
                    ctype = line.split(":", 1)[1].strip()
                elif low.startswith("content-length:"):
                    expected = line.split(":", 1)[1].strip()
        if status == 401:
            raise RuntimeError(
                "Pollinations rejected the API key (401). Get a key at "
                "https://enter.pollinations.ai/keys or run: "
                "npx @pollinations/cli auth login\n" + raw[:400].decode(errors="replace")
            )
        if status >= 400:
            raise _Retryable("HTTP %d: %s" % (status, raw[:300].decode(errors="replace")))
        _check_complete(expected, raw)
        return ctype, raw
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _request(path, payload, timeout=180, attempts=4):
    """POST JSON to the gen API, return (content_type, raw_bytes).

    Retries when the body arrives shorter than Content-Length. The first
    attempts use urllib; later attempts fall back to curl when available,
    which survives proxies that truncate urllib streams.
    """
    url = GEN_BASE + path
    last_err = None
    for attempt in range(attempts):
        try:
            if attempt >= 2 and shutil.which("curl"):
                return _post_curl(url, payload, timeout)
            return _post_urllib(url, payload, timeout)
        except _Retryable as e:
            last_err = e
            if attempt < attempts - 1:
                time.sleep(2 * (attempt + 1))
    raise RuntimeError("Request to %s failed after %d attempts: %s" % (path, attempts, last_err))


def chat(messages, model=None, temperature=0.8):
    """One chat completion. Returns the assistant text."""
    _, raw = _request(
        "/v1/chat/completions",
        {"model": model or TEXT_MODEL, "messages": messages, "temperature": temperature},
    )
    data = json.loads(raw.decode())
    return data["choices"][0]["message"]["content"]


def generate_image(prompt, model=None, size="1024x1024", seed=None):
    """Generate one image. Returns raw image bytes."""
    payload = {"model": model or IMAGE_MODEL, "prompt": prompt, "size": size}
    if seed is not None:
        payload["seed"] = seed
    ctype, raw = _request("/v1/images/generations", payload, timeout=300)
    if "json" in ctype:
        item = (json.loads(raw.decode()).get("data") or [{}])[0]
        if item.get("b64_json"):
            return base64.b64decode(item["b64_json"])
        if item.get("url"):
            with urllib.request.urlopen(item["url"], timeout=120) as resp:
                return resp.read()
        raise RuntimeError("Image response had neither b64_json nor url.")
    return raw


def text_to_speech(text, model=None, voice=None):
    """Synthesize speech. Returns MP3 bytes."""
    ctype, raw = _request(
        "/v1/audio/speech",
        {"model": model or TTS_MODEL, "input": text, "voice": voice or TTS_VOICE},
    )
    if "json" in ctype:
        raise RuntimeError("Speech endpoint returned JSON instead of audio: " + raw[:200].decode(errors="replace"))
    return raw


def image_extension(raw):
    if raw[:3] == b"\xff\xd8\xff":
        return ".jpg"
    if raw[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png"
    if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        return ".webp"
    return ".jpg"
