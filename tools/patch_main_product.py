#!/usr/bin/env python3
"""
One-shot patch for sections/main-product.liquid:
  1. remove the stray quote after the dews-pdp.js script tag
  2. replace the broken `dimensions` / `material_care` block renderers
  3. replace their schema definitions with the configurable, variant-aware ones

Idempotent: re-running on an already patched file changes nothing.
"""
import json
import re
import sys

PATH = "sections/main-product.liquid"
src = open(PATH, encoding="utf-8").read()
orig = src

# ---------------------------------------------------------------- 1. stray "
src = src.replace(
    """  <script src="{{ 'dews-pdp.js' | asset_url }}" defer="defer"></script>"\n""",
    """  <script src="{{ 'dews-pdp.js' | asset_url }}" defer="defer"></script>\n""",
)

# ------------------------------------------------- 2. block renderers
NEW_RENDER = """                {%- when 'dimensions' -%}
                  {%- assign dews_dims_id = 'DewsDimensions-' | append: section.id -%}
                  {%- render 'dews-spec-block',
                    product: product,
                    block: block,
                    settings: block.settings,
                    layout: 'tiles',
                    element_id: dews_dims_id,
                    section_id: section.id
                  -%}
                {%- when 'material_care' -%}
                  {%- assign dews_mat_id = 'DewsMaterials-' | append: section.id -%}
                  {%- render 'dews-spec-block',
                    product: product,
                    block: block,
                    settings: block.settings,
                    layout: 'rows',
                    element_id: dews_mat_id,
                    section_id: section.id
                  -%}
"""

render_re = re.compile(
    r"[ \t]*\{%- when 'dimensions' -%\}.*?(?=[ \t]*\{%- when 'buy_buttons' -%\})",
    re.DOTALL,
)
src, n_render = render_re.subn(NEW_RENDER, src, count=1)
if n_render != 1:
    sys.exit("!! could not locate the dimensions..buy_buttons render span")

# ------------------------------------------------- 3. schema
def rows_schema(prefix, spec):
    """spec = list of (label, key, fallback_default, size_map_info)"""
    out = []
    for i, (label, key, enabled) in enumerate(spec, start=1):
        p = f"row_{i}"
        out += [
            {"type": "header", "content": f"Row {i}"},
            {"type": "checkbox", "id": f"{p}_enabled", "label": "Show this row", "default": enabled},
            {"type": "text", "id": f"{p}_label", "label": "Label", "default": label},
            {
                "type": "text",
                "id": f"{p}_key",
                "label": "Metafield key",
                "default": key,
                "info": "Key of the VARIANT metafield, without the namespace.",
            },
            {
                "type": "text",
                "id": f"{p}_fallback",
                "label": "Static fallback value",
                "info": "Used only when no metafield value exists for the variant.",
            },
            {
                "type": "textarea",
                "id": f"{p}_size_map",
                "label": "Per-option fallback map",
                "info": (
                    "Optional. One entry per line as  Option value: value  — matched "
                    "against the variant's option values (e.g. its Size). Used only when "
                    "no metafield value exists. Example:\n1 Seater: 38 in\n2 Seater: 58 in"
                ),
            },
        ]
    return out


def common_head(heading_default, note_default, with_columns):
    s = [
        {
            "type": "paragraph",
            "content": (
                "Values follow the SELECTED VARIANT. Priority for every row, most "
                "specific first: variant metafield \u2192 per-option fallback map \u2192 "
                "product metafield \u2192 static fallback. Metafields must be defined on "
                "VARIANTS (Admin \u2192 Settings \u2192 Custom data \u2192 Products \u2192 "
                "Variants tab), otherwise every size shows the same value. Switch on "
                "\u201cShow debug table\u201d below to see exactly where each value came from."
            ),
        },
        {"type": "text", "id": "heading", "label": "Heading", "default": heading_default},
    ]
    if with_columns:
        s.append(
            {
                "type": "select",
                "id": "columns",
                "label": "Tiles per row",
                "options": [
                    {"value": 2, "label": "2"},
                    {"value": 3, "label": "3"},
                    {"value": 4, "label": "4"},
                ],
                "default": 4,
            }
        )
    if note_default is not None:
        s.append({"type": "text", "id": "note", "label": "Note under the values", "default": note_default})
    s += [
        {"type": "header", "content": "Data source"},
        {
            "type": "select",
            "id": "source",
            "label": "How the values are stored",
            "options": [
                {"value": "rows", "label": "One metafield per row (recommended)"},
                {"value": "json", "label": "Auto rows from one JSON metafield"},
            ],
            "default": "rows",
        },
        {
            "type": "text",
            "id": "namespace",
            "label": "Metafield namespace",
            "default": "custom",
        },
        {
            "type": "text",
            "id": "json_key",
            "label": "JSON metafield key",
            "default": "dimensions",
            "info": "Only used when “How the values are stored” is set to JSON. Each property of that JSON becomes a row.",
        },
    ]
    return s


def common_tail():
    return [
        {"type": "header", "content": "Advanced"},
        {
            "type": "text",
            "id": "unavailable_text",
            "label": "Message for unavailable combinations",
            "default": "This combination is currently unavailable.",
        },
        {
            "type": "checkbox",
            "id": "debug",
            "label": "Show debug table",
            "info": "Theme editor only. Lists every variant with its resolved value and where it came from (V=variant, P=product, S=size map, F=fallback).",
            "default": False,
        },
    ]


dimensions_block = {
    "type": "dimensions",
    "name": "Dimensions (variant-aware)",
    "limit": 1,
    "settings": common_head("Dimensions", "All dimensions in inches", True)
    + rows_schema(
        "dimensions",
        [
            ("Width", "width", True),
            ("Depth", "depth", True),
            ("Height", "height", True),
            ("Seat height", "seat_height", True),
            ("Weight", "weight", False),
            ("Seating capacity", "capacity", False),
        ],
    )
    + common_tail(),
}

material_block = {
    "type": "material_care",
    "name": "Material & Care (variant-aware)",
    "limit": 1,
    "settings": common_head("Material & Care", None, False)
    + rows_schema(
        "material",
        [
            ("Material", "material", True),
            ("Finish", "finish", True),
            ("Care", "care", True),
            ("Assembly", "assembly", False),
            ("Warranty", "warranty", False),
            ("Colour", "color", False),
        ],
    )
    + common_tail(),
}


def dump(block):
    return json.dumps(block, indent=2, ensure_ascii=True)


schema_re = re.compile(
    r"[ \t]*\{\n[ \t]*\"type\": \"dimensions\",.*?\n    \},\n"
    r"[ \t]*\{\n[ \t]*\"type\": \"material_care\",.*?\n    \},\n",
    re.DOTALL,
)
replacement = dump(dimensions_block) + ",\n" + dump(material_block) + ",\n"
# indent every line by 4 spaces to match the surrounding schema style
replacement = "".join(("    " + ln if ln.strip() else ln) + "\n" for ln in replacement.splitlines())

src, n_schema = schema_re.subn(lambda m: replacement, src, count=1)
if n_schema != 1:
    sys.exit("!! could not locate the dimensions/material_care schema span")

# ---------------------------------------------------------------- validate
m = re.search(r"{% schema %}(.*?){% endschema %}", src, re.DOTALL)
if not m:
    sys.exit("!! schema block not found after patch")
try:
    parsed = json.loads(m.group(1))
except Exception as e:
    sys.exit(f"!! patched schema is not valid JSON: {e}")

types = [b.get("type") for b in parsed["blocks"]]
assert "dimensions" in types and "material_care" in types, types
assert types.count("dimensions") == 1 and types.count("material_care") == 1, types

if src != orig:
    open(PATH, "w", encoding="utf-8").write(src)
    print("patched OK — schema valid, blocks:", len(parsed["blocks"]))
    print("note: only the two target block entries were rewritten; the rest of")
    print("      the schema text is byte-identical to the original.")
else:
    print("already patched, no change")
