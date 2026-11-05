#!/usr/bin/env python3
"""Parse raw Figma REST API JSON into frontend-friendly structured data.

Input : figma-data/raw/node_1_20_full.json  (GET /v1/files/{key}/nodes?ids=1:20)
Output: figma-data/processed/design-tree.json
        figma-data/processed/design-tokens.json

Every parsed node keeps its complete original payload under "raw", so no
source attribute is ever silently dropped.
"""
import json
import math
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
RAW = BASE / "raw" / "node_1_20_full.json"
OUT = BASE / "processed"

LAYOUT_KEYS = [
    "layoutMode", "primaryAxisSizingMode", "counterAxisSizingMode",
    "primaryAxisAlignItems", "counterAxisAlignItems",
    "paddingLeft", "paddingRight", "paddingTop", "paddingBottom",
    "itemSpacing", "counterAxisSpacing", "layoutWrap",
]
CONSTRAINT_KEYS = ["constraints"]
EFFECT_KEYS = ["effects"]


def rgba_to_hex(c):
    if not isinstance(c, dict):
        return None
    r = round(c.get("r", 0) * 255)
    g = round(c.get("g", 0) * 255)
    b = round(c.get("b", 0) * 255)
    a = c.get("a", 1)
    hexv = f"#{r:02X}{g:02X}{b:02X}"
    if a < 1:
        hexv += f"{round(a * 255):02X}"
    return hexv


def paint_summary(paint):
    """Normalize a fill/stroke paint, keeping a reference to the raw value."""
    if not isinstance(paint, dict):
        return {"raw": paint}
    out = {"type": paint.get("type"), "visible": paint.get("visible", True),
           "opacity": paint.get("opacity", 1), "raw": paint}
    if paint.get("type") == "SOLID":
        out["color"] = rgba_to_hex(paint.get("color"))
        out["colorRGBA"] = paint.get("color")
    elif paint.get("type") == "IMAGE":
        out["imageRef"] = paint.get("imageRef")
        out["scaleMode"] = paint.get("scaleMode")
        out["imageTransform"] = paint.get("imageTransform")
    elif paint.get("type") in ("GRADIENT_LINEAR", "GRADIENT_RADIAL",
                               "GRADIENT_ANGULAR", "GRADIENT_DIAMOND"):
        out["gradientStops"] = [
            {"color": rgba_to_hex(s.get("color")), "position": s.get("position")}
            for s in paint.get("gradientStops", [])
        ]
        out["gradientTransform"] = paint.get("gradientTransform")
    return out


def parse_node(node, parent_bbox=None):
    n = {
        "id": node.get("id"),
        "name": node.get("name"),
        "type": node.get("type"),
        "visible": node.get("visible", True),
        "locked": node.get("locked", False),
    }

    bbox = node.get("absoluteBoundingBox")
    if bbox:
        n["box"] = {
            "x": bbox.get("x"), "y": bbox.get("y"),
            "width": bbox.get("width"), "height": bbox.get("height"),
        }
        if parent_bbox:
            n["box"]["relativeX"] = bbox["x"] - parent_bbox["x"]
            n["box"]["relativeY"] = bbox["y"] - parent_bbox["y"]
    else:
        n["box"] = None

    layout = {k: node[k] for k in LAYOUT_KEYS if k in node}
    if layout:
        n["autoLayout"] = layout

    for k in CONSTRAINT_KEYS:
        if k in node:
            n[k] = node[k]

    if node.get("opacity", 1) != 1:
        n["opacity"] = node["opacity"]
    if node.get("blendMode") not in (None, "NORMAL"):
        n["blendMode"] = node["blendMode"]

    if "fills" in node:
        n["fills"] = [paint_summary(p) for p in node["fills"]]
    if "strokes" in node and node["strokes"]:
        n["strokes"] = [paint_summary(p) for p in node["strokes"]]
        if "strokeWeight" in node:
            n["strokeWeight"] = node["strokeWeight"]
        if "strokeAlign" in node:
            n["strokeAlign"] = node["strokeAlign"]
        if node.get("strokeDashArray"):
            n["strokeDashArray"] = node["strokeDashArray"]
    if "background" in node and node["background"]:
        n["background"] = [paint_summary(p) for p in node["background"]]
    if node.get("backgroundColor"):
        n["backgroundColor"] = rgba_to_hex(node["backgroundColor"])

    for k in ("cornerRadius", "rectangleCornerRadii", "cornerSmoothing",
              "strokeTopWeight", "strokeBottomWeight", "strokeLeftWeight",
              "strokeRightWeight"):
        if k in node:
            n.setdefault("corner", {})[k] = node[k]

    for k in EFFECT_KEYS:
        if node.get(k):
            n["effects"] = node[k]

    if node.get("type") == "TEXT":
        st = node.get("style", {})
        n["text"] = {
            "characters": node.get("characters"),
            "fontFamily": st.get("fontFamily"),
            "fontPostScriptName": st.get("fontPostScriptName"),
            "fontStyle": st.get("fontStyle"),
            "fontWeight": st.get("fontWeight"),
            "fontSize": st.get("fontSize"),
            "lineHeightPx": st.get("lineHeightPx"),
            "lineHeightPercent": st.get("lineHeightPercent"),
            "letterSpacing": st.get("letterSpacing"),
            "textAlignHorizontal": st.get("textAlignHorizontal"),
            "textAlignVertical": st.get("textAlignVertical"),
            "textAutoResize": st.get("textAutoResize"),
            "textDecoration": st.get("textDecoration"),
            "textCase": st.get("textCase"),
            "fills": [paint_summary(p) for p in node.get("fills", [])],
        }
        if node.get("styleOverrideTable"):
            n["text"]["styleOverrideTable"] = node["styleOverrideTable"]

    if node.get("type") == "VECTOR":
        n["vector"] = {
            "fillRule": node.get("fillRule"),
            "strokeCap": node.get("strokeCap"),
            "strokeJoin": node.get("strokeJoin"),
            "has fillGeometry": bool(node.get("fillGeometry")),
            "has strokeGeometry": bool(node.get("strokeGeometry")),
        }

    if node.get("exportSettings"):
        n["exportSettings"] = node["exportSettings"]
    if node.get("componentId"):
        n["componentId"] = node["componentId"]
    if node.get("boundVariables"):
        n["boundVariables"] = node["boundVariables"]
    if node.get("interactions"):
        n["interactions"] = node["interactions"]

    n["raw"] = node  # complete original payload, nothing dropped

    children = node.get("children")
    if children:
        n["children"] = [parse_node(c, bbox) for c in children]
    return n


def collect_stats(node, stats):
    stats["total"] += 1
    stats["byType"][node["type"]] = stats["byType"].get(node["type"], 0) + 1
    if node.get("text"):
        stats["texts"] += 1
        stats["characters"] += len(node["text"]["characters"] or "")
    for p in (node.get("fills") or []) + (node.get("strokes") or []):
        c = p.get("color")
        if c:
            stats["colors"].add(c)
    if node.get("text"):
        for p in node["text"].get("fills") or []:
            if p.get("color"):
                stats["colors"].add(p["color"])
    if node.get("backgroundColor"):
        stats["colors"].add(node["backgroundColor"])
    if node.get("background"):
        for p in node["background"]:
            if p.get("color"):
                stats["colors"].add(p["color"])
    if node.get("corner", {}).get("cornerRadius"):
        stats["radii"].add(node["corner"]["cornerRadius"])
    st = (node.get("text") or {})
    if st.get("fontSize"):
        stats["fontSizes"].add(st["fontSize"])
    for c in node.get("children") or []:
        collect_stats(c, stats)


def build_tokens(root):
    colors, fonts, radii, effects = {}, {}, {}, {}

    def walk(node):
        locs = []
        for group_key, paints in (("fill", node.get("fills")),
                                  ("stroke", node.get("strokes")),
                                  ("background", node.get("background"))):
            for p in paints or []:
                if p.get("color"):
                    locs.append((group_key, p["color"]))
        if node.get("backgroundColor"):
            locs.append(("backgroundColor", node["backgroundColor"]))
        t = node.get("text") or {}
        for p in t.get("fills") or []:
            if p.get("color"):
                locs.append(("text", p["color"]))
        for kind, hexv in locs:
            entry = colors.setdefault(hexv, {"hex": hexv, "usages": []})
            entry["usages"].append({"nodeId": node["id"], "kind": kind})

        if t.get("fontSize"):
            key = f"{t.get('fontFamily')} {t.get('fontSize')}px/{t.get('fontWeight')} {t.get('fontStyle') or ''}".strip()
            entry = fonts.setdefault(key, {
                "fontFamily": t.get("fontFamily"),
                "fontPostScriptName": t.get("fontPostScriptName"),
                "fontSize": t.get("fontSize"),
                "fontWeight": t.get("fontWeight"),
                "fontStyle": t.get("fontStyle"),
                "lineHeightPx": t.get("lineHeightPx"),
                "letterSpacing": t.get("letterSpacing"),
                "usages": [],
            })
            entry["usages"].append({"nodeId": node["id"],
                                    "text": (t.get("characters") or "")[:40]})

        r = (node.get("corner") or {}).get("cornerRadius")
        if r:
            radii.setdefault(str(r), {"radius": r, "usages": []})["usages"].append(
                {"nodeId": node["id"]})

        for e in node.get("effects") or []:
            key = json.dumps(e, sort_keys=True, ensure_ascii=False)
            effects.setdefault(key, {"effect": e, "usages": []})["usages"].append(
                {"nodeId": node["id"]})

        for c in node.get("children") or []:
            walk(c)

    walk(root)
    return {
        "colors": sorted(colors.values(), key=lambda x: x["hex"]),
        "typography": sorted(fonts.values(),
                             key=lambda x: (x["fontFamily"] or "", x["fontSize"] or 0)),
        "cornerRadii": sorted(radii.values(), key=lambda x: x["radius"]),
        "effects": list(effects.values()),
    }


def main():
    data = json.loads(RAW.read_text(encoding="utf-8"))
    doc = data["nodes"]["1:20"]["document"]
    tree = parse_node(doc)
    tree["source"] = {
        "fileKey": "D0jjN7Twkq0DGm3ZJvQabz",
        "endpoint": "/v1/files/D0jjN7Twkq0DGm3ZJvQabz/nodes?ids=1:20",
        "rawFile": "figma-data/raw/node_1_20_full.json",
    }

    stats = {"total": 0, "byType": {}, "texts": 0, "characters": 0,
             "colors": set(), "radii": set(), "fontSizes": set()}
    collect_stats(tree, stats)

    OUT.mkdir(exist_ok=True)
    (OUT / "design-tree.json").write_text(
        json.dumps(tree, ensure_ascii=False, indent=2), encoding="utf-8")
    tokens = build_tokens(tree)
    tokens["_stats"] = {
        "nodeCount": stats["total"],
        "nodeTypes": stats["byType"],
        "textNodes": stats["texts"],
        "textCharacters": stats["characters"],
        "colorCount": len(stats["colors"]),
        "cornerRadiusCount": len(stats["radii"]),
        "fontSizeCount": len(stats["fontSizes"]),
    }
    (OUT / "design-tokens.json").write_text(
        json.dumps(tokens, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(tokens["_stats"], ensure_ascii=False, indent=2))
    print("colors:", sorted(stats["colors"]))
    print("radii:", sorted(stats["radii"]), "fontSizes:", sorted(stats["fontSizes"]))


if __name__ == "__main__":
    main()
