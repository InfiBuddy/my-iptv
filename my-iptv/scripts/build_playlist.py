"""Rebuild playlist.m3u from the latest upstream playlists, keeping only the
channels listed in selection.json. Stream URLs are always taken fresh from
upstream, so URL changes made by iptv-org flow through automatically."""
import json
import os
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))
import m3u  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def epg_url():
    if os.environ.get("EPG_URL"):
        return os.environ["EPG_URL"]
    repo = os.environ.get("GITHUB_REPOSITORY")
    branch = os.environ.get("GITHUB_REF_NAME", "main")
    return f"https://raw.githubusercontent.com/{repo}/{branch}/epg.xml" if repo else ""


def stream_ok(entry, timeout=10):
    try:
        req = urllib.request.Request(entry["url"], headers=m3u.request_headers(entry))
        with urllib.request.urlopen(req, timeout=timeout) as r:
            if r.status >= 400:
                return False
            head = r.read(4096)
            ctype = r.headers.get("Content-Type", "").lower()
            return b"#EXTM3U" in head or "video" in ctype or "mpegurl" in ctype or "octet" in ctype
    except Exception:
        return False


def main():
    sel = json.load(open(os.path.join(ROOT, "selection.json"), encoding="utf-8"))
    opts = {"streams_per_channel": 1, "check_streams": True, "clean_names": True, **sel.get("options", {})}
    keep = list(dict.fromkeys(sel.get("keep", [])))  # ordered, unique

    entries = []
    for src in sel["sources"]:
        try:
            entries += m3u.parse(m3u.fetch_text(src), src)
            print(f"loaded {src}")
        except Exception as ex:
            print(f"WARNING: could not load {src}: {ex}")
    if not entries:
        sys.exit("No upstream entries loaded; keeping the previous playlist.")

    by_key, by_base = {}, {}
    for e in entries:
        by_key.setdefault(e["key"], []).append(e)
        by_base.setdefault(m3u.base_id(e["key"]), []).append(e)

    chosen, missing = {}, []
    for k in keep:
        cands = by_key.get(k) or (by_base.get(m3u.base_id(k)) if not k.startswith("name:") else None)
        if not cands:
            missing.append(k)
            continue
        seen, uniq = set(), []
        for c in cands:
            if c["url"] not in seen:
                seen.add(c["url"])
                uniq.append(c)
        chosen[k] = uniq

    health = {}
    if opts["check_streams"]:
        all_c = [c for cs in chosen.values() for c in cs]
        with ThreadPoolExecutor(max_workers=16) as pool:
            for c, ok in zip(all_c, pool.map(stream_ok, all_c)):
                health[c["url"]] = ok

    def rank(c):
        geo = any("geo" in t for t in c["tags"])
        return (not health.get(c["url"], True), geo, -c["quality"])

    url_epg = epg_url()
    out = [f'#EXTM3U x-tvg-url="{url_epg}" url-tvg="{url_epg}"' if url_epg else "#EXTM3U"]
    report = []
    for k in keep:
        if k not in chosen:
            continue
        streams = sorted(chosen[k], key=rank)[: max(1, int(opts["streams_per_channel"]))]
        for i, s in enumerate(streams):
            name = m3u.clean_name(s["name"]) if opts["clean_names"] else s["name"]
            if i:
                name += f" (backup {i + 1})"
            attrs = dict(s["attrs"])
            attrs["tvg-id"] = "" if k.startswith("name:") else k
            attrs["tvg-name"] = name
            attrs["group-title"] = s["group"]
            attr_str = " ".join(f'{a}="{v}"' for a, v in attrs.items() if v != "" or a == "tvg-id")
            out.append(f"#EXTINF:-1 {attr_str},{name}")
            out.extend(s["extra"])
            out.append(s["url"])
        report.append({"key": k, "name": m3u.clean_name(streams[0]["name"]), "streams_available": len(chosen[k]),
                       "best_stream_ok": health.get(streams[0]["url"])})

    open(os.path.join(ROOT, "playlist.m3u"), "w", encoding="utf-8").write("\n".join(out) + "\n")
    status = {
        "updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "channels": len(report),
        "missing_upstream": missing,
        "unreachable_from_github": [r["key"] for r in report if r["best_stream_ok"] is False],
        "detail": report,
    }
    json.dump(status, open(os.path.join(ROOT, "status.json"), "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(f"playlist.m3u: {len(report)} channels, {len(missing)} missing upstream")


if __name__ == "__main__":
    main()
