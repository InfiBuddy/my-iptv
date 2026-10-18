# my-iptv

A personal, self-updating IPTV playlist with a TV guide, built from iptv-org.

- `index.html` – Channel Picker. Load any M3U, keep/remove single channels or whole groups, save.
- `selection.json` – what you keep (channel IDs, not URLs).
- `.github/workflows/update.yml` – every 6 hours (and right after you save) it:
  1. downloads the latest upstream playlist(s) and keeps only your channels → `playlist.m3u`
  2. tests each stream and puts a working one first
  3. grabs 2 days of programme data for those channels from Indian guide sites (Tata Play, Dish TV, Airtel, JioTV, Zee5…) → `epg.xml`
- `status.json` – last run: channel count, channels missing upstream, streams that failed the test.

Because the selection stores channel IDs, a channel that changes its stream URL is picked up automatically on the next run.

## Setup (10 minutes, one time)

1. **Create a public repo** on GitHub, e.g. `my-iptv`, and upload everything in this folder (including the `.github` folder).
   Public is required so TV Mate can read the raw files without a login.
2. **Run it once**: repo → *Actions* → enable workflows → *Update playlist and EPG* → *Run workflow*. Takes ~5–10 min.
   When it finishes, `playlist.m3u`, `epg.xml` and `status.json` appear in the repo.
3. **TV Mate** → Add playlist → M3U playlist → URL:
   `https://raw.githubusercontent.com/OWNER/my-iptv/main/playlist.m3u`
   The playlist header already points to the guide, so EPG is added automatically. If it isn't, add EPG source
   `https://raw.githubusercontent.com/OWNER/my-iptv/main/epg.xml`.
   In TV Mate's free version the existing playlist's settings are locked, so add this as a new playlist and disable the old one.
   Set *Update playlist* / *Update EPG* to "on app start" (or every 12 h).
4. **Picker online (optional but handy)**: repo → *Settings* → *Pages* → Deploy from branch `main`, folder `/ (root)`.
   Open `https://OWNER.github.io/my-iptv/`. Owner/repo are filled in for you.
5. **Token for the Save button**: GitHub → Settings → Developer settings → Fine-grained tokens → Generate.
   Repository access: only `my-iptv`. Permissions: *Contents → Read and write*. Paste it into the picker once and tick "Remember".

You can also open `index.html` straight from your computer; it works the same way.

## Notes

- **Channels without a guide**: the run log ("Grab EPG" step) lists them. Some small channels exist on no guide site.
- **Guide sites refusing GitHub's US servers**: each channel has two guide sources and the build keeps the previous `epg.xml` if a whole run fails. If guides stay empty, run the same two commands on any always-on machine in India (see the workflow file).
- **"unreachable_from_github" in status.json**: those streams failed the test from GitHub's US servers. Many Indian streams are India-only, so they are still kept and usually play fine at home.
- Add more sources (e.g. `https://iptv-org.github.io/iptv/categories/news.m3u`) as extra lines in the picker's URL box.
