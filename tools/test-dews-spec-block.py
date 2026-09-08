#!/usr/bin/env python3
"""
Renders the REAL snippets/dews-spec-block.liquid (plus dews-spec-resolve and
dews-mf-value) against fake Shopify product data and asserts on the output.

This is the test that would have caught the original bug: it json.loads() the
embedded per-variant map, so invalid JSON, metafield-object leakage or missing
per-variant values all fail loudly.

Run: python3 tools/test-dews-spec-block.py
"""
import html as html_mod
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from liquid_render import Drop, Metafield, Metafields, Renderer  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R = Renderer([os.path.join(ROOT, "snippets")])

checks = 0
failures = 0


def ok(cond, label):
    global checks, failures
    checks += 1
    print(("  ✓ " if cond else "  ✗ ") + label)
    if not cond:
        failures += 1


def eq(actual, expected, label):
    ok(actual == expected, label + ("" if actual == expected else f"   (got {actual!r}, want {expected!r})"))


# ---------------------------------------------------------------- fixtures
def mf(value, t="single_line_text_field"):
    return Metafield(value, t)


def variant(vid, title, option, custom=None):
    return Drop({
        "id": vid,
        "title": title,
        "options": [option],
        "sku": f"SKU-{vid}",
        "metafields": Metafields({"custom": custom or {}}),
    })


def product(variants, selected_index=0, product_custom=None, title="Sheesham Sofa"):
    return Drop({
        "id": 999,
        "title": title,
        "handle": "sheesham-sofa",
        "variants": variants,
        "selected_or_first_available_variant": variants[selected_index] if variants else None,
        "selected_variant": None,
        "metafields": Metafields({"custom": product_custom or {}}),
    })


def settings(**over):
    base = {
        "heading": "Dimensions",
        "note": "All dimensions in inches",
        "columns": 4,
        "source": "rows",
        "namespace": "custom",
        "json_key": "dimensions",
        "unavailable_text": "This combination is currently unavailable.",
        "debug": False,
    }
    for i in range(1, 7):
        base[f"row_{i}_enabled"] = False
        base[f"row_{i}_label"] = None
        base[f"row_{i}_key"] = None
        base[f"row_{i}_fallback"] = None
        base[f"row_{i}_size_map"] = None
    base.update({
        "row_1_enabled": True, "row_1_label": "Width", "row_1_key": "width",
        "row_2_enabled": True, "row_2_label": "Depth", "row_2_key": "depth",
        "row_3_enabled": True, "row_3_label": "Height", "row_3_key": "height",
        "row_4_enabled": True, "row_4_label": "Seat height", "row_4_key": "seat_height",
    })
    base.update(over)
    return Drop(base)


BLOCK = Drop({"id": "blk1", "shopify_attributes": 'id="shopify-block-blk1" class="shopify-block"'})


def render(prod, st, layout="tiles", design_mode=False, element_id="DewsDimensions-main"):
    return R.render_file("dews-spec-block", {
        "product": prod,
        "block": BLOCK,
        "settings": st,
        "layout": layout,
        "element_id": element_id,
        "section_id": "main",
        "request": Drop({"design_mode": design_mode}),
    })


# ------------------------------------------------------------- output parsing
JSON_RE = re.compile(r'<script type="application/json" data-dews-spec-json>(.*?)</script>', re.DOTALL)


def embedded_json(out):
    m = JSON_RE.search(out)
    if not m:
        return None, None
    raw = m.group(1)
    try:
        return json.loads(raw), raw
    except Exception as e:  # noqa: BLE001
        return ("INVALID:" + str(e)), raw


def row(out, key):
    pat = re.compile(
        r'<(li|div)\b([^>]*?)data-dim-key="' + re.escape(key) + r'"([^>]*)>(.*?)</\1>',
        re.DOTALL,
    )
    m = pat.search(out)
    if not m:
        return None
    attrs = m.group(3)
    inner = m.group(4)
    vm = re.search(r'data-dim-val[^>]*>(.*?)</', inner, re.DOTALL)
    return {
        "hidden": "hidden" in attrs.split(),
        "value": html_mod.unescape(vm.group(1).strip()) if vm else None,
        "label": html_mod.unescape(re.search(r'dews-spec__label">([^<]*)<', inner).group(1)) if "dews-spec__label" in inner else None,
    }


# ================================================================ TESTS
print("\n— 1. Variant metafields: 3 sofa sizes, all different ——————————")
sofa = product([
    variant(4001, "1 Seater", "1 Seater", {"width": mf("38 in"), "depth": mf("34 in"), "height": mf("31 in"), "seat_height": mf("18 in")}),
    variant(4002, "2 Seater", "2 Seater", {"width": mf("58 in"), "depth": mf("34 in"), "height": mf("31 in"), "seat_height": mf("18 in")}),
    variant(4003, "3 Seater", "3 Seater", {"width": mf("78 in"), "depth": mf("34 in"), "height": mf("31 in"), "seat_height": mf("18 in")}),
])
out = render(sofa, settings())
data, raw = embedded_json(out)

ok(isinstance(data, dict), "embedded JSON parses as an object")
ok("<dews-variant-info" in out, "custom element rendered")
eq(row(out, "width")["value"], "38 in", "first paint shows the SELECTED variant (1 Seater)")
eq(row(out, "width")["hidden"], False, "row with a value is visible")
eq(data["byRow"]["width"]["4001"], "38 in", "map: 1 Seater width")
eq(data["byRow"]["width"]["4002"], "58 in", "map: 2 Seater width  <-- the thing that was broken")
eq(data["byRow"]["width"]["4003"], "78 in", "map: 3 Seater width")
eq(data["byRow"]["depth"]["4002"], "34 in", "map: shared depth still present")
eq(len(data["byRow"]), 4, "all four enabled rows are in the map")
ok("4002" in data["byRow"]["width"], "variant ids are QUOTED string keys (valid JSON)")
ok('"width"' in raw and "Metafield" not in raw, "no metafield object leaked into the JSON")

print("\n— 2. A row with no value for one variant only ————————————————")
chair = product([
    variant(5001, "Small", "Small", {"width": mf("20 in"), "seat_height": mf("18 in")}),
    variant(5002, "Large", "Large", {"width": mf("26 in")}),  # no seat_height
])
out = render(chair, settings(row_2_enabled=False, row_3_enabled=False))
data, _ = embedded_json(out)
eq(data["byRow"]["seat_height"]["5001"], "18 in", "small chair has seat height")
eq(data["byRow"]["seat_height"]["5002"], None, "large chair emits null (row hides in JS)")
eq(row(out, "seat_height")["value"], "18 in", "selected variant renders its own seat height")

print("\n— 3. Fallback chain: variant > product > size map > static ————")
mixed = product(
    [
        variant(6001, "1 Seater", "1 Seater", {"width": mf("38 in")}),          # variant wins
        variant(6002, "2 Seater", "2 Seater", {}),                               # product / map / static
        variant(6003, "3 Seater", "3 Seater", {}),
    ],
    product_custom={"width": mf("PRODUCT-W")},
)
st = settings(
    row_2_enabled=False, row_3_enabled=False, row_4_enabled=False,
    row_1_size_map="2 Seater: 58 in\n3 Seater: 78 in",
    row_1_fallback="99 in",
)
out = render(mixed, st)
data, _ = embedded_json(out)
eq(data["byRow"]["width"]["6001"], "38 in", "level 1 — variant metafield wins")
eq(data["byRow"]["width"]["6002"], "58 in", "level 3 — per-size map beats the product value")
eq(data["byRow"]["width"]["6003"], "78 in", "level 3 — per-size map, second entry")

print("\n— 4. Only a product metafield exists (the classic mistake) ————")
prodonly = product(
    [variant(7001, "1 Seater", "1 Seater", {}), variant(7002, "2 Seater", "2 Seater", {})],
    product_custom={"width": mf("58 in")},
)
out = render(prodonly, settings(row_2_enabled=False, row_3_enabled=False, row_4_enabled=False))
data, _ = embedded_json(out)
eq(data["byRow"]["width"]["7001"], "58 in", "level 2 — product metafield used")
eq(data["byRow"]["width"]["7002"], "58 in", "level 2 — same value for every variant (expected)")

print("\n— 5. No metafields at all, only the static fallback ——————————")
bare = product([variant(8001, "One", "One", {}), variant(8002, "Two", "Two", {})])
out = render(bare, settings(row_2_enabled=False, row_3_enabled=False, row_4_enabled=False, row_1_fallback="42 in"))
data, _ = embedded_json(out)
eq(data["byRow"]["width"]["8001"], "42 in", "level 4 — static fallback")

print("\n— 6. Nothing configured anywhere -> renders nothing / editor hint")
empty = product([variant(9001, "One", "One", {})])
st = settings(row_2_enabled=False, row_3_enabled=False, row_4_enabled=False)
out_store = render(empty, st, design_mode=False)
out_editor = render(empty, st, design_mode=True)
eq(out_store.strip(), "", "storefront renders NOTHING when there is no data")
ok("dews-spec--empty" in out_editor, "theme editor shows the empty-state placeholder")
ok("VARIANTS" in out_editor or "variant" in out_editor, "placeholder tells the merchant to use variant metafields")

print("\n— 7. Debug table (theme editor only) ————————————————————————")
out = render(sofa, settings(debug=True), design_mode=True)
ok("dews-spec__debug-table" in out, "debug table rendered in design mode")
eq(out.count('data-src="V"'), 12, "all 12 cells (4 rows x 3 variants) report source V")
out_store = render(sofa, settings(debug=True), design_mode=False)
ok("dews-spec__debug" not in out_store, "debug table is NEVER rendered on the storefront")

print("\n— 8. rows layout (Material & Care) ——————————————————————————")
mat = product([
    variant(1001, "Oak / Beige", "Oak", {"material": mf("Sheesham wood"), "finish": mf("Natural lacquer"), "care": mf("Wipe with a dry cloth.\nAvoid direct sunlight.")}),
    variant(1002, "Walnut / Grey", "Walnut", {"material": mf("Sheesham wood"), "finish": mf("Dark walnut stain"), "care": mf("Wipe with a dry cloth.\nRe-oil once a year.")}),
])
st = settings(
    heading="Material & Care", note=None,
    row_1_label="Material", row_1_key="material",
    row_2_label="Finish", row_2_key="finish",
    row_3_label="Care", row_3_key="care",
    row_4_enabled=False,
)
out = render(mat, st, layout="rows", element_id="DewsMaterials-main")
data, _ = embedded_json(out)
ok("dews-spec--rows" in out, "rows layout class applied")
eq(data["byRow"]["finish"]["1002"], "Dark walnut stain", "finish differs per variant")
ok("\n" in data["byRow"]["care"]["1002"], "multi-line care text preserved in the map")
eq(row(out, "care")["value"], "Wipe with a dry cloth.\nAvoid direct sunlight.", "multi-line care rendered for the selected variant")
ok("dews-spec__val--multi" in out, "multi-line value gets the pre-line class")

print("\n— 9. JSON source mode (one JSON metafield per variant) ————————")
jsonp = product([
    variant(1101, "1 Seater", "1 Seater", {"dimensions": Metafield({"Width": "38 in", "Depth": "34 in"}, "json")}),
    variant(1102, "2 Seater", "2 Seater", {"dimensions": Metafield({"Width": "58 in", "Depth": "36 in"}, "json")}),
])
out = render(jsonp, settings(source="json", json_key="dimensions"), element_id="DewsDimensions-main")
data, raw = embedded_json(out)
ok(isinstance(data, dict), "JSON-mode map parses")
eq(data["byVariant"]["1102"]["Width"], "58 in", "JSON mode: 2 Seater width")
eq(row(out, "Width")["value"], "38 in", "JSON mode: rows come from the selected variant's JSON keys")
eq(len(re.findall(r'data-dim-key=', out)), 2, "JSON mode: one row per JSON property")

print("\n— 10. Hostile values must not break the JSON ————————————————")
nasty = product([
    variant(1201, 'Quote " and <tag>', "A", {"width": mf('24" W <script>alert(1)</script>')}),
    variant(1202, "Backslash \\ and newline", "B", {"width": mf("line1\nline2 \\ end")}),
])
out = render(nasty, settings(row_2_enabled=False, row_3_enabled=False, row_4_enabled=False))
data, raw = embedded_json(out)
ok(isinstance(data, dict), f"JSON still parses with quotes/tags/backslashes/newlines ({raw[:40]}...)")
eq(data["byRow"]["width"]["1201"], '24" W <script>alert(1)</script>', "value round-trips exactly")
ok("</script>" not in raw, "no raw </script> inside the JSON payload (would break the tag)")
ok("&lt;script&gt;" in out, "displayed value is HTML-escaped by Liquid")
eq(row(out, "width")["value"], '24" W <script>alert(1)</script>', "escaped value round-trips after unescaping")

print("\n— 11. Non-text metafield types —————————————————————————————")
typed = product([
    variant(1301, "A", "A", {
        "width": Metafield(38, "number_integer"),
        "depth": Metafield(["34 in", "36 in"], "list.single_line_text_field"),
        "height": Metafield(31.5, "number_decimal"),
        "seat_height": Metafield(True, "boolean"),
    }),
])
out = render(typed, settings())
data, _ = embedded_json(out)
eq(data["byRow"]["width"]["1301"], "38", "number_integer rendered as text")
eq(data["byRow"]["depth"]["1301"], "34 in, 36 in", "list metafield joined")
eq(data["byRow"]["seat_height"]["1301"], "Yes", "boolean rendered as Yes/No")

print("\n— 12. Single-variant / default-variant products —————————————")
solo = product([variant(1401, "Default Title", "Default Title", {"width": mf("38 in")})])
out = render(solo, settings(row_2_enabled=False, row_3_enabled=False, row_4_enabled=False))
data, _ = embedded_json(out)
eq(data["byRow"]["width"]["1401"], "38 in", "works for a product with one variant")
ok("data-variant-id=\"1401\"" in out, "data-variant-id matches the only variant")

print("\n— 13. Custom namespace + custom keys ———————————————————————")
custom_ns = product([
    Drop({"id": 1501, "title": "1 Seater", "options": ["1 Seater"],
          "metafields": Metafields({"specs": {"w": mf("38 in")}})}),
    Drop({"id": 1502, "title": "2 Seater", "options": ["2 Seater"],
          "metafields": Metafields({"specs": {"w": mf("58 in")}})}),
])
out = render(custom_ns, settings(
    namespace="specs",
    row_1_key="w", row_2_enabled=False, row_3_enabled=False, row_4_enabled=False,
))
data, _ = embedded_json(out)
ok(isinstance(data, dict), "custom namespace renders valid JSON")
eq(data["byRow"]["w"]["1502"], "58 in", "bracket lookup resolves a non-default namespace")

print("\n— 14. Block attributes + heading + note ————————————————")
out = render(sofa, settings(heading="Product Dimensions", note="Measured by hand, ±1 in"))
ok('id="shopify-block-blk1"' in out, "block.shopify_attributes preserved (theme editor selection)")
ok("Product Dimensions" in out and "Measured by hand" in out, "heading and note rendered")
ok('data-section-id="main"' in out, "data-section-id emitted for the JS cross-talk guard")
ok("dews-spec--cols-4" in out, "columns setting applied")

print("\n— 15. JSON mode: a key that exists on only SOME variants ———————")
partial = product([
    variant(1601, "1 Seater", "1 Seater", {"dimensions": Metafield({"Width": "38 in", "Depth": "34 in"}, "json")}),
    variant(1602, "2 Seater", "2 Seater", {"dimensions": Metafield({"Width": "58 in", "Depth": "36 in", "Arm Height": "24 in"}, "json")}),
])
out = render(partial, settings(source="json", json_key="dimensions"))
data, _ = embedded_json(out)
keys = re.findall(r'data-dim-key="([^"]+)"', out)
eq(keys, ["Width", "Depth", "Arm Height"], "rows are the UNION of every variant's JSON keys")
eq(data["byVariant"]["1601"].get("Arm Height"), None, "1 Seater has no Arm Height -> null")
eq(data["byVariant"]["1602"]["Arm Height"], "24 in", "2 Seater does have Arm Height")
eq(row(out, "Arm Height")["hidden"], True, "row rendered but hidden for the selected variant that lacks it")
eq(row(out, "Width")["value"], "38 in", "selected variant's own Width still shown")

print(f"\n{checks - failures}/{checks} checks passed")
sys.exit(1 if failures else 0)
