# Phone thumbnails — self-hosted mirror

## Why this exists

About 80% of the catalogue's lock photos live on Flickr
(`live.staticflickr.com`). When the phone loads a long list of them, Flickr
rate-limits your connection's IP address and answers **429 Too Many Requests** —
so the thumbnails go blank. It hits the Lock Hunter phone app *and* lpubelts.com
at the same time (both point at the same Flickr images), which is why the
photos vanish on the phone but are fine on the computer.

The fix: mirror the thumbnails onto your own GitHub Pages site once, and the app
loads them from there instead of hammering Flickr. Flickr is only touched as a
fallback for a lock that hasn't been mirrored yet (one added since your last
run), so nothing is ever worse than before.

## One-time setup

1. **Download the thumbnails** — on your **PC** (its connection reaches Flickr
   fine; the phone's is the one being throttled), **double-click
   `MIRROR-THUMBS.bat`**. Keep it in the same folder as `mirror_thumbs.py`
   (both ship in the Lock Hunter zip, or run it from the source folder so it can
   use the app's own Python).

   A console window opens and stays open while it works. It writes a `thumbs/`
   folder next to the script. It's safe to stop and re-run — anything already
   downloaded is skipped, and if Flickr starts throttling mid-run it waits and
   keeps going. A full first run is ~800 images and a few minutes. If any fail,
   just run it again to pick them up.

   > Prefer a terminal? `python mirror_thumbs.py` does the same thing. (Running
   > the `.py` by **double-click** flashes a window open and shut — use the
   > `.bat`, or a terminal, so you can see the output.)

2. **Put `thumbs/` in your phone repo and push.** Copy the whole `thumbs/`
   folder into the same GitHub repo that serves your phone page
   (`ckaralis85-spec/Lockhunter-phone`, the one with `index.html`), commit, and
   push. GitHub Pages then serves them at
   `https://ckaralis85-spec.github.io/Lockhunter-phone/thumbs/<lock id>.jpg` —
   exactly where the app looks.

That's it. Reload the phone app and the list fills from GitHub instead of
Flickr.

## If your repo or Pages URL is different

The app builds each thumbnail URL from **one constant** near the top of the
`LOCKS view` section in `phonepage/index.html` (and the identical
`lockhunter_phone.html`):

```js
const THUMB_BASE = "https://ckaralis85-spec.github.io/Lockhunter-phone/thumbs/";
```

Change that one line to match wherever your `thumbs/` folder ends up being
served, and keep the folder named `thumbs` (or change both to match).

## Keeping it updated — `UPDATE-THUMBS.bat`

The mirror is a snapshot, so LPU's new locks and any photo they swap out won't
appear until you refresh it. `UPDATE-THUMBS.bat` does the whole refresh in one
click: it pulls the latest, downloads only the **new and changed** thumbnails
(it tracks each one's source in `thumbs/_sources.json`, so it re-fetches a photo
LPU replaced — not just missing ones), then commits and pushes just the
thumbnail changes. If nothing changed, it does nothing.

**Set it up once:**

1. Copy `UPDATE-THUMBS.bat` **and** `mirror_thumbs.py` into your **cloned
   phone-repo folder** — the one git made, with the hidden `.git` folder,
   `index.html`, and `thumbs/` in it (e.g. `Downloads\Lockhunter-phone`). If you
   uploaded through the web instead of cloning, make a clone first:
   `git clone https://github.com/ckaralis85-spec/Lockhunter-phone.git`
2. Double-click `UPDATE-THUMBS.bat`. The **first** push opens a one-time GitHub
   sign-in window; after that Windows remembers it.

That's the whole routine — run it whenever you like (say once a month). Between
refreshes, any brand-new lock just loads from its original source (Flickr etc.),
a trickle small enough not to trip the rate limit.

### Optional: run it automatically (Windows Task Scheduler)

1. Open **Task Scheduler** → **Create Basic Task**.
2. Name it "Update Lock Hunter thumbnails", pick **Monthly** (or Weekly).
3. Action: **Start a program** → Program/script: browse to your
   `UPDATE-THUMBS.bat`. In **Add arguments** type `/auto` (this skips the
   "press Enter" pause so it can run unattended).
4. Finish. Do one **manual** run first (double-click it once) so the GitHub
   sign-in is cached — after that the scheduled runs push on their own.

## What is *not* mirrored

- **The desktop app** still loads lock photos directly from their source. It
  runs on your PC, whose connection isn't throttled, and it loads one photo at
  a time — so it never trips the limit and doesn't need the mirror.
- **Full-size photos** aren't mirrored (they'd be gigabytes). The list and the
  detail card both use the small thumbnail, which is what gets mirrored.
