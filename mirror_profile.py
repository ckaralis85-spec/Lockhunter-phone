#!/usr/bin/env python3
"""Mirror YOUR Lock Hunter collection into a static collection.json you commit to
the phone repo (served by GitHub Pages), so the hosted phone page can load your
Owned + Wishlist even when it can't read LPU directly.

WHY: the hosted phone page (index.html on GitHub Pages) reads your collection
straight from LPU in the browser. That needs LPU to answer a cross-origin
browser request. Their NEW user API went down (HTTP 503, Sept 2026) and their
OLD profile endpoint — which still works — sends no cross-origin header, so a
browser can't read it. Your PC has no such restriction: it CAN read the old
endpoint. So the PC mirrors your collection to a plain file the phone reads from
your own GitHub Pages site (same origin, no cross-origin problem, no LPU call
from the phone at all). This is the exact trick MIRROR-THUMBS uses for photos.

The phone loads collection.json ONLY as a fallback, when its live LPU read
fails — so the moment LPU's API is back, the phone uses the live data again and
this file just sits there as a safety net.

RUN THIS ON YOUR PC. It reads the profile id Lock Hunter already has saved
(~/.lockhunter/config.json), fetches your Owned + Wishlist from LPU's profile
service, and writes ./collection.json next to it. To pull + commit + push it to
your phone repo in one go, use UPDATE-THUMBS.bat (it runs this for you).

    python mirror_profile.py                 # use the id Lock Hunter has saved
    python mirror_profile.py --id <memberid> # mirror a specific member id
    python mirror_profile.py --out collection.json

Only the Python standard library is used, so plain `python mirror_profile.py`
works with no installs.
"""
import argparse
import datetime
import json
import os
import re
import sys
import urllib.error
import urllib.request

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# The same two endpoints Lock Hunter's desktop reads, in the same order: the new
# open user API first (used again automatically the moment LPU restores it), then
# the old token'd service that stayed up when the new one 503'd. cdfac03d is Lock
# Hunter's own app token — LPU issued it and echoes it in every reply, so it is
# not a secret. Neither call is a database read.
NEW_API = "https://explore.lpubelts.com/services/api/v1/users/"
OLD_API = "https://explore.lpubelts.com/API/profile/?token=cdfac03d&id="
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

_RE_UID = re.compile(r"[Pp][Rr][Oo][Ff][Ii][Ll][Ee]/([A-Za-z0-9_-]{10,})")
_RE_ID_PARAM = re.compile(r"[?&][Ii][Dd]=([A-Za-z0-9_-]{10,})")
_RE_BARE = re.compile(r"^[A-Za-z0-9]{24,36}$")


def extract_uid(text):
    s = str(text or "").strip()
    m = _RE_UID.search(s) or _RE_ID_PARAM.search(s)
    if m:
        return m.group(1)
    return s if _RE_BARE.match(s) else None


def uid_from_config():
    """The member id Lock Hunter already has saved, so no id need be typed."""
    cfg = os.path.join(os.path.expanduser("~"), ".lockhunter", "config.json")
    try:
        with open(cfg, encoding="utf-8") as fh:
            return extract_uid(json.load(fh).get("profile_url") or "")
    except Exception:
        return None


def _get_json(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": _UA,
        "Accept": "application/json, text/plain, */*",
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def _collections(data):
    """(own, wish) from EITHER shape: new {"data":{collections}} or old flat
    {"collections",...}. safelocksOwn / scorecard / picked are ignored, exactly
    as the app ignores them."""
    payload = data.get("data") if isinstance(data, dict) else None
    if not isinstance(payload, dict) and isinstance(data, dict) \
            and isinstance(data.get("collections"), dict):
        payload = data
    if not isinstance(payload, dict):
        raise ValueError("unexpected response shape from LPU")
    cols = payload.get("collections") or {}
    if not isinstance(cols, dict):
        raise ValueError("unexpected response shape from LPU")

    def ids(key):
        v = cols.get(key)
        return sorted({str(x) for x in v if isinstance(x, (str, int)) and str(x)}) \
            if isinstance(v, list) else []
    return ids("own"), ids("wishlist"), str(payload.get("userId") or "")


def fetch_collection(uid):
    problems = []
    for label, url in (("new user API", NEW_API + uid),
                       ("profile service", OLD_API + uid)):
        try:
            data = _get_json(url)
        except Exception as ex:
            problems.append(f"{label}: {ex}")
            continue
        own, wish, got = _collections(data)
        if got and got != uid:
            raise SystemExit(
                f"Refusing to mirror: LPU returned member {got}, not {uid}.")
        return own, wish
    raise SystemExit("Could not read your collection from LPU.\n  "
                     + "\n  ".join(problems)
                     + "\n(If both say 503, LPU's service is down — try later.)")


def main():
    ap = argparse.ArgumentParser(description="Mirror your LPU collection to collection.json")
    ap.add_argument("--id", dest="uid", default=None,
                    help="member id to mirror (default: the one Lock Hunter saved)")
    ap.add_argument("--out", default=os.path.join(SCRIPT_DIR, "collection.json"),
                    help="output file (default: collection.json next to this script)")
    args = ap.parse_args()

    uid = extract_uid(args.uid) if args.uid else uid_from_config()
    if not uid:
        print("No profile id found. Open Lock Hunter and connect your LPU profile "
              "first, or pass one:  python mirror_profile.py --id <memberid>")
        return 1

    print(f"Mirroring collection for {uid} …")
    own, wish = fetch_collection(uid)
    out = {
        "uid": uid,
        "own": own,
        "wish": wish,
        "counts": {"own": len(own), "wish": len(wish)},
        "updated": datetime.datetime.now().astimezone().replace(microsecond=0).isoformat(),
        "source": "lpubelts.com profile service, mirrored by mirror_profile.py",
    }
    tmp = args.out + ".part"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, args.out)
    print(f"Wrote {args.out}: {len(own)} owned, {len(wish)} wishlist "
          f"(as of {out['updated']}).")
    print("Commit + push collection.json to your phone repo (UPDATE-THUMBS.bat "
          "does this for you), and the hosted phone page will read it whenever "
          "it can't reach LPU live.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except KeyboardInterrupt:
        print("\nStopped.")
        sys.exit(1)
