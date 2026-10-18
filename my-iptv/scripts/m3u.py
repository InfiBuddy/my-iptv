"""Small M3U parser shared by the build scripts (stdlib only)."""
import re
import urllib.request

ATTR_RE = re.compile(r'([A-Za-z0-9_-]+)="([^"]*)"')
QUALITY_RE = re.compile(r'\((\d{3,4})[pi]\)')
TAG_RE = re.compile(r'\[([^\]]+)\]')
DEFAULT_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")


def fetch_text(url, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": DEFAULT_UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def clean_name(name):
    name = QUALITY_RE.sub("", name)
    name = TAG_RE.sub("", name)
    return re.sub(r"\s+", " ", name).strip()


def channel_key(entry):
    """Stable identity of a channel: tvg-id, or the cleaned name if it has none."""
    tid = entry["attrs"].get("tvg-id", "").strip()
    return tid if tid else "name:" + clean_name(entry["name"]).lower()


def base_id(key):
    return key.split("@", 1)[0]


def parse(text, source=""):
    entries, cur, extra = [], None, []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#EXTM3U"):
            continue
        if line.startswith("#EXTINF:"):
            body = line[len("#EXTINF:"):]
            attrs = dict(ATTR_RE.findall(body))
            leftover = ATTR_RE.sub("", body)
            name = leftover.split(",", 1)[1].strip() if "," in leftover else ""
            cur, extra = {"attrs": attrs, "name": name}, []
            continue
        if line.startswith("#"):
            # #EXTVLCOPT / #KODIPROP / #EXTGRP etc. belong to the next URL
            if cur is not None:
                extra.append(line)
            continue
        if cur is None:
            continue
        q = QUALITY_RE.search(cur["name"])
        tags = [t.strip().lower() for t in TAG_RE.findall(cur["name"])]
        groups = [g.strip() for g in cur["attrs"].get("group-title", "").split(";") if g.strip()]
        entries.append({
            **cur,
            "url": line,
            "extra": extra,
            "quality": int(q.group(1)) if q else 0,
            "tags": tags,
            "group": groups[0] if groups else "Undefined",
            "source": source,
        })
        cur, extra = None, []
    for e in entries:
        e["key"] = channel_key(e)
    return entries


def request_headers(entry):
    ua, ref = entry["attrs"].get("http-user-agent") or DEFAULT_UA, entry["attrs"].get("http-referrer")
    for x in entry["extra"]:
        if x.lower().startswith("#extvlcopt:http-user-agent="):
            ua = x.split("=", 1)[1]
        elif x.lower().startswith("#extvlcopt:http-referrer="):
            ref = x.split("=", 1)[1]
    h = {"User-Agent": ua}
    if ref:
        h["Referer"] = ref
    return h
