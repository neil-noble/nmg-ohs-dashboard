"""Authenticated GET against the PeopleTray API, with retries."""
import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path

BASE_URL = "https://api-peopletray.azurewebsites.net"
# Shared with the other NMG projects; the key is on line 2, under a label line.
KEY_FILE = Path(r"C:\claude\PeopleTray DAS\reference\PT API Key for NMG.txt")
ATTEMPTS = 4


def load_key(env=os.environ, key_file=KEY_FILE):
    key = (env.get("PT_API_KEY") or "").strip()
    if key:
        return key
    try:
        return Path(key_file).read_text(encoding="utf-8-sig").splitlines()[1].strip()
    except (OSError, IndexError):
        raise RuntimeError(f"No PeopleTray key: set PT_API_KEY or provide {key_file}") from None


def get(path, params=None, opener=urllib.request.urlopen, sleep=time.sleep):
    url = BASE_URL + path + ("?" + urllib.parse.urlencode(params) if params else "")
    request = urllib.request.Request(url, headers={"X-API-Key": load_key()})
    last_error = None
    for attempt in range(ATTEMPTS):
        if attempt:
            sleep(5 * 2 ** (attempt - 1))
        try:
            with opener(request, timeout=120) as response:
                return json.loads(response.read())
        except (OSError, ValueError) as error:    # URLError and HTTPError are OSErrors
            last_error = error
    raise RuntimeError(f"PeopleTray {path} failed after {ATTEMPTS} attempts: {last_error}")
