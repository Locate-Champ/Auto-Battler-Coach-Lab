import os
import re
import requests

BASE = "https://raw.communitydragon.org/latest/game/assets/ux/traiticons/"
OUT_DIR = "trait_icons_set16"
os.makedirs(OUT_DIR, exist_ok=True)

html = requests.get(BASE).text

# Pull all Set 16 trait icon filenames from the directory listing.
files = re.findall(r'(trait_icon_16_[^"]+?\.png)', html)
teamups = re.findall(r'(teamup_trait_[^"]*tft_(?:set16|16_3)\.png)', html)

all_files = sorted(set(files + teamups))

print("Found:", len(all_files), "files")

for fn in all_files:
    url = BASE + fn
    path = os.path.join(OUT_DIR, fn)
    r = requests.get(url)
    r.raise_for_status()
    with open(path, "wb") as f:
        f.write(r.content)

print("Saved to:", OUT_DIR)
