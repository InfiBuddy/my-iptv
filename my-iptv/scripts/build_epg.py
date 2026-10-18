"""EPG builder for the channels in playlist.m3u, using iptv-org/epg grabbers.

  python scripts/build_epg.py prepare <path-to-iptv-org-epg-clone>
      -> writes custom.channels.xml (up to 2 guide sources per channel)
  (then run: npm run grab --- --channels=../custom.channels.xml --output=../guides/{site}.xml)
  python scripts/build_epg.py merge
      -> writes epg.xml, taking each channel from the best source that returned data
"""
import glob
import json
import os
import re
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(__file__))
import m3u  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Indian guide sources first; anything else that covers the channel comes after.
PRIORITY = ["tataplay.com", "dishtv.in", "airtelxstream.in", "jiotv.com", "zee5.com",
            "epg.iptvx.one", "sky.com"]
SOURCES_PER_CHANNEL = 2
MAP_FILE = os.path.join(ROOT, "guides", "_map.json")


def playlist_channels():
    text = open(os.path.join(ROOT, "playlist.m3u"), encoding="utf-8").read()
    chans = {}
    for e in m3u.parse(text):
        tid = e["attrs"].get("tvg-id", "")
        if tid and tid not in chans:
            chans[tid] = {"name": m3u.clean_name(e["name"]),
                          "logo": e["attrs"].get("tvg-logo", "")}
    return chans


def broken_sites(epg_dir):
    path = os.path.join(epg_dir, "SITES.md")
    if not os.path.exists(path):
        return set()
    bad = set()
    for row in open(path, encoding="utf-8"):
        m = re.search(r'<a href="sites/([^"]+)">', row)
        if m and "🔴" in row:
            bad.add(m.group(1))
    return bad


def prepare(epg_dir):
    bad = broken_sites(epg_dir)
    index = {}
    for f in glob.glob(os.path.join(epg_dir, "sites", "*", "*.channels.xml")):
        try:
            root = ET.parse(f).getroot()
        except ET.ParseError:
            continue
        for ch in root.iter("channel"):
            xid, site = ch.get("xmltv_id") or "", ch.get("site") or ""
            if not xid or not ch.get("site_id") or site in bad:
                continue
            index.setdefault(m3u.base_id(xid), []).append(
                {"xid": xid, "site": site, "site_id": ch.get("site_id"), "lang": ch.get("lang") or "en",
                 "label": (ch.text or "").strip()})

    def site_rank(site):
        return PRIORITY.index(site) if site in PRIORITY else len(PRIORITY)

    out = ET.Element("channels")
    mapping, unmatched = {}, []
    for tid, info in playlist_channels().items():
        cands = index.get(m3u.base_id(tid), [])
        # exact feed match first (e.g. @SD), then other feeds of the same channel
        cands.sort(key=lambda c: (c["xid"] != tid, site_rank(c["site"]), "hd" in c["label"].lower()))
        picked = []
        for c in cands:
            if c["site"] in [p["site"] for p in picked]:
                continue
            picked.append(c)
            if len(picked) == SOURCES_PER_CHANNEL:
                break
        if not picked:
            unmatched.append(tid)
            continue
        mapping[tid] = [p["site"] for p in picked]
        for p in picked:
            el = ET.SubElement(out, "channel", site=p["site"], lang=p["lang"], xmltv_id=tid, site_id=p["site_id"])
            el.text = info["name"]
    os.makedirs(os.path.dirname(MAP_FILE), exist_ok=True)
    ET.indent(out)
    ET.ElementTree(out).write(os.path.join(ROOT, "custom.channels.xml"), encoding="utf-8", xml_declaration=True)
    json.dump(mapping, open(MAP_FILE, "w"), indent=1)
    print(f"EPG sources found for {len(mapping)} channels; none for: {', '.join(unmatched) or '-'}")


def merge():
    chans = playlist_channels()
    mapping = json.load(open(MAP_FILE)) if os.path.exists(MAP_FILE) else {}
    progs_by_site = {}
    for f in glob.glob(os.path.join(ROOT, "guides", "*.xml")):
        site = os.path.basename(f)[:-4]
        try:
            root = ET.parse(f).getroot()
        except ET.ParseError:
            continue
        for p in root.iter("programme"):
            progs_by_site.setdefault(site, {}).setdefault(p.get("channel"), []).append(p)

    tv = ET.Element("tv", {"generator-info-name": "my-iptv"})
    programmes, covered = [], []
    for tid, info in chans.items():
        for site in mapping.get(tid, []):
            got = progs_by_site.get(site, {}).get(tid)
            if got:
                programmes += got
                covered.append(f"{tid} <- {site}")
                break
    if not programmes and os.path.exists(os.path.join(ROOT, "epg.xml")):
        print("No programmes grabbed this run; keeping the previous epg.xml")
        return
    for tid, info in chans.items():
        ch = ET.SubElement(tv, "channel", id=tid)
        ET.SubElement(ch, "display-name").text = info["name"]
        if info["logo"]:
            ET.SubElement(ch, "icon", src=info["logo"])
    tv.extend(programmes)
    ET.indent(tv)
    ET.ElementTree(tv).write(os.path.join(ROOT, "epg.xml"), encoding="utf-8", xml_declaration=True)
    print(f"epg.xml: {len(covered)}/{len(chans)} channels with programmes, {len(programmes)} programmes")
    for c in covered:
        print("  " + c)


if __name__ == "__main__":
    if sys.argv[1:2] == ["prepare"]:
        prepare(sys.argv[2])
    elif sys.argv[1:2] == ["merge"]:
        merge()
    else:
        sys.exit(__doc__)
