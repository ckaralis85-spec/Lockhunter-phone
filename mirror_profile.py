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

COMPARE ON THE HOSTED PHONE. Compare needs the OTHER collector's collection, and
the hosted page can't read another member from LPU any more than it can read your
own (same cross-origin block). So this script also mirrors compare targets into
collections/<id>.json — the phone reads those same-origin, exactly the way it
reads your own. Name each target the way you'd type it into Compare (a name or a
profile link):

    python mirror_profile.py --also Sidepicks --also "Some Name"
    # or list them, one per line, in compare_targets.txt next to this script

Your own collection is always written to BOTH collection.json and
collections/<your id>.json. Only the Python standard library is used, so plain
`python mirror_profile.py` works with no installs.
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
# The public leaderboard (displayName -> id), so a compare target can be given by
# NAME, exactly like the app's Compare box. It sends a cross-origin header, so a
# browser can read it — but it holds only counts, not lock ids, which is why the
# collections themselves have to be mirrored.
LEADERBOARD = "https://explore.lpubelts.com/data/leaderboardData.json"
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


def fetch_collection(uid, strict=True):
    """(own, wish) for a member, new user API first then the old profile service.
    strict=True (your own id): a wrong member or a total failure is fatal
    (SystemExit) — your file is never written from someone else's data. strict=
    False (a compare target): the same problems raise ValueError so the caller can
    skip that one target and carry on with the rest."""
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
            msg = f"LPU returned member {got}, not {uid}."
            if strict:
                raise SystemExit("Refusing to mirror: " + msg)
            raise ValueError(msg)
        return own, wish
    detail = "\n  ".join(problems) + \
        "\n(If both say 503, LPU's service is down — try later.)"
    if strict:
        raise SystemExit("Could not read your collection from LPU.\n  " + detail)
    raise ValueError("could not be read from LPU — " + "; ".join(problems))


# --- compare targets: other collectors, so the hosted phone can Compare them ---
# The hosted page can't read another member from LPU (same cross-origin block the
# mirror already solves for your own collection). So the PC mirrors each target's
# collection to collections/<id>.json too, and the phone reads it same-origin.
# A target may be given by NAME, exactly like the app's Compare box: the name is
# resolved to an id off LPU's public leaderboard (displayName -> id), highest
# score wins a tie — the same rule resolveCollector uses on the phone.
def resolve_name(name):
    """A collector NAME -> (uid, display_name) via the public leaderboard, or
    (None, None) if no one has that name. Raises ValueError if the leaderboard
    itself can't be read."""
    s = str(name or "").strip()
    if not s:
        return None, None
    try:
        d = _get_json(LEADERBOARD)
    except Exception as ex:
        raise ValueError(f"couldn't read the LPU leaderboard to look up “{s}”: {ex}")
    arr = d if isinstance(d, list) else \
        ((d.get("data") if isinstance(d, dict) else None) or [])
    best = None
    for x in arr:
        if not isinstance(x, dict):
            continue
        nm = str(x.get("displayName") or "").strip()
        if not nm or nm.lower() == "no display name" or not x.get("id"):
            continue
        if nm.lower() != s.lower():
            continue
        raw = x.get("recordedLocks") or x.get("own") or x.get("locksCollection") or 0
        try:
            score = int(raw)
        except (TypeError, ValueError):
            score = 0
        if best is None or score > best[2]:
            best = (str(x.get("id")), nm, score)
    return (best[0], best[1]) if best else (None, None)


def resolve_target(text):
    """A compare target given as a link/id OR a name -> (uid, who). A link or bare
    id wins immediately (who is None); anything else is looked up as a name."""
    uid = extract_uid(text)
    if uid:
        return uid, None
    return resolve_name(text)


def read_targets(explicit, targets_file):
    """Compare targets to mirror: every --also value, then each non-blank,
    non-comment line of compare_targets.txt. Order is kept and duplicates dropped
    (case-insensitively); names are resolved later, not here."""
    out, seen = [], set()

    def add(v):
        v = str(v or "").strip()
        if not v or v.startswith("#"):
            return
        if v.lower() not in seen:
            seen.add(v.lower())
            out.append(v)

    for v in (explicit or []):
        add(v)
    try:
        with open(targets_file, encoding="utf-8") as fh:
            for line in fh:
                add(line)
    except OSError:
        pass
    return out


_OWN_SOURCE = "lpubelts.com profile service, mirrored by mirror_profile.py"
_TARGET_SOURCE = "lpubelts.com profile service (compare target), mirrored by mirror_profile.py"


def write_collection(path, uid, own, wish, source):
    """Write one {uid, own, wish, counts, updated, source} file atomically, making
    the parent folder if needed. Same shape the phone reads for every member."""
    out = {
        "uid": uid,
        "own": own,
        "wish": wish,
        "counts": {"own": len(own), "wish": len(wish)},
        "updated": datetime.datetime.now().astimezone().replace(microsecond=0).isoformat(),
        "source": source,
    }
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    tmp = path + ".part"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, path)
    return out


def main():
    ap = argparse.ArgumentParser(
        description="Mirror your LPU collection (and any compare targets) to JSON "
                    "the hosted phone page can read.")
    ap.add_argument("--id", dest="uid", default=None,
                    help="member id to mirror (default: the one Lock Hunter saved)")
    ap.add_argument("--out", default=os.path.join(SCRIPT_DIR, "collection.json"),
                    help="output file for YOUR collection (default: collection.json "
                         "next to this script). collections/<id>.json is written "
                         "alongside it.")
    ap.add_argument("--also", action="append", default=[], metavar="NAME_OR_LINK",
                    help="also mirror this collector so the hosted phone can Compare "
                         "them without a PC — a name (e.g. Sidepicks) or a profile "
                         "link. Repeatable.")
    ap.add_argument("--targets", default=os.path.join(SCRIPT_DIR, "compare_targets.txt"),
                    help="a file of extra compare targets, one name or link per line "
                         "(default: compare_targets.txt next to this script).")
    args = ap.parse_args()

    uid = extract_uid(args.uid) if args.uid else uid_from_config()
    if not uid:
        print("No profile id found. Open Lock Hunter and connect your LPU profile "
              "first, or pass one:  python mirror_profile.py --id <memberid>")
        return 1

    base_dir = os.path.dirname(os.path.abspath(args.out))
    collections_dir = os.path.join(base_dir, "collections")

    print(f"Mirroring collection for {uid} …")
    own, wish = fetch_collection(uid)                       # your own: strict
    saved = write_collection(args.out, uid, own, wish, _OWN_SOURCE)
    write_collection(os.path.join(collections_dir, uid + ".json"),
                     uid, own, wish, _OWN_SOURCE)
    print(f"Wrote {args.out}: {len(own)} owned, {len(wish)} wishlist "
          f"(as of {saved['updated']}).")

    targets = read_targets(args.also, args.targets)
    if targets:
        print(f"Mirroring {len(targets)} compare target(s) so the phone can Compare "
              "them without a PC …")
        done, failed = 0, []
        for raw in targets:
            try:
                tuid, who = resolve_target(raw)
            except Exception as ex:                         # leaderboard unreadable
                failed.append(f"{raw}: {ex}")
                continue
            if not tuid:
                failed.append(f"{raw}: no collector by that name on the leaderboard "
                              "(check the spelling, or use their profile link)")
                continue
            if tuid == uid:
                continue                                    # that's you — already done
            try:
                town, twish = fetch_collection(tuid, strict=False)
            except Exception as ex:
                failed.append(f"{who or raw}: {ex}")
                continue
            write_collection(os.path.join(collections_dir, tuid + ".json"),
                             tuid, town, twish, _TARGET_SOURCE)
            done += 1
            print(f"  + {who or tuid}: {len(town)} owned, {len(twish)} wishlist")
        print(f"Mirrored {done} of {len(targets)} compare target(s)"
              + (f", {len(failed)} skipped:" if failed else "."))
        for f in failed:
            print("  - skipped " + f)

    print("Commit + push to your phone repo (UPDATE-THUMBS.bat does this for you), "
          "and the hosted phone page will read your collection — and any mirrored "
          "compare target — whenever it can't reach LPU live.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except KeyboardInterrupt:
        print("\nStopped.")
        sys.exit(1)
