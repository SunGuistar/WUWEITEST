#!/usr/bin/env python3
"""Download exported assets from Figma image-export responses and build
figma-data/processed/asset-map.json.

Reads  : figma-data/raw/_tmp/exp_svg.json, exp_png.json (images-endpoint responses)
Writes : figma-data/assets/svg/*.svg, figma-data/assets/images/*.png,
         figma-data/processed/asset-map.json
Existing files are reused, never re-downloaded.
"""
import json
import re
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
TMP = BASE / "raw"
SVG_RESP = TMP / "export-images_svg_response.json"
PNG_RESP = TMP / "export-images_png_response.json"
SVG_DIR = BASE / "assets" / "svg"
IMG_DIR = BASE / "assets" / "images"
OUT = BASE / "processed"

SVG_IDS = ["1:27", "1:31", "1:32", "1:33", "1:34", "1:37", "1:38", "1:35", "1:44"]
PNG_IDS = ["1:21"]
# node id -> semantic file name (from design-tree node names)
NAMES = {
    "1:27": "icon-upload-cloud",
    "1:31": "step-dot-1-outer",
    "1:32": "step-dot-2-outer",
    "1:33": "step-dot-3-outer",
    "1:34": "step-dot-1-inner",
    "1:37": "step-dot-2-inner",
    "1:38": "step-dot-3-inner",
    "1:35": "icon-check-1",
    "1:44": "icon-check-2",
    "1:21": "illustration-resume-scene",
}


def slug(node_id):
    return f"{node_id.replace(':', '-')}_{NAMES.get(node_id, 'asset')}"


def main():
    svg_resp = json.loads(SVG_RESP.read_text(encoding="utf-8"))
    png_resp = json.loads(PNG_RESP.read_text(encoding="utf-8"))

    asset_map = {"source": {
        "fileKey": "D0jjN7Twkq0DGm3ZJvQabz",
        "endpoint": "/v1/images/{fileKey}?ids=...&format=svg|png",
        "note": "URLs from Figma image export API; downloaded and stored locally "
                "so downstream tools do not need API access or quota."},
        "assets": []}

    failures = []
    for fmt, resp, out_dir, ids in (
        ("svg", svg_resp, SVG_DIR, SVG_IDS),
        ("png", png_resp, IMG_DIR, PNG_IDS),
    ):
        images = resp.get("images") or {}
        for nid in ids:
            url = images.get(nid)
            if not url:
                failures.append({"id": nid, "reason": "no URL in export response"})
                continue
            path = out_dir / f"{slug(nid)}.{fmt}"
            entry = {"nodeId": nid, "name": NAMES.get(nid),
                     "format": fmt, "file": str(path.relative_to(BASE)),
                     "source": "figma-images-api"}
            if path.exists() and path.stat().st_size > 0:
                entry["status"] = "reused-existing"
            else:
                try:
                    req = urllib.request.Request(url, headers={"User-Agent": "curl/8"})
                    data = urllib.request.urlopen(req, timeout=60).read()
                    path.write_bytes(data)
                    entry["status"] = "downloaded"
                except Exception as e:  # noqa: BLE001
                    entry["status"] = "failed"
                    entry["error"] = str(e)[:200]
                    failures.append({"id": nid, "reason": str(e)[:200]})
            entry["bytes"] = path.stat().st_size if path.exists() else 0
            asset_map["assets"].append(entry)

    OUT.mkdir(exist_ok=True)
    (OUT / "asset-map.json").write_text(
        json.dumps(asset_map, ensure_ascii=False, indent=2), encoding="utf-8")

    ok = [a for a in asset_map["assets"] if a["status"] != "failed"]
    print(f"assets ok: {len(ok)}, failed: {len(failures)}")
    for a in asset_map["assets"]:
        print(f"  {a['status']:17} {a['file']} ({a['bytes']} bytes)")


if __name__ == "__main__":
    main()
