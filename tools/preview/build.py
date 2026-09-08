#!/usr/bin/env python3
"""
Builds tools/preview/index.html — a self-contained demo of the variant-aware
Dimensions / Material & Care blocks.

Everything is REAL:
  * the markup comes from rendering snippets/dews-spec-block.liquid with the
    minimal Liquid engine in tools/liquid_render.py
  * the behaviour comes from the actual assets/dews-pdp.js
  * the event bus comes from the actual assets/constants.js + assets/pubsub.js
  * the styling comes from the actual assets/component-dews-product.css

The only thing mocked is Dawn's product-info.js: it does exactly the two things
Dawn does after its section fetch — set input[name="id"] and publish
variantChange.

Run: python3 tools/preview/build.py
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from liquid_render import Drop, Metafield, Metafields, Renderer  # noqa: E402

R = Renderer([os.path.join(ROOT, "snippets")])


def mf(v, t="single_line_text_field"):
    return Metafield(v, t)


def variant(vid, title, custom, price):
    return Drop({
        "id": vid, "title": title, "options": [title], "price": price,
        "available": True, "sku": f"DW-{vid}",
        "metafields": Metafields({"custom": {k: (v if isinstance(v, Metafield) else mf(v)) for k, v in custom.items()}}),
    })


def make_product(variants, product_custom=None, title="Amara Cane Sofa"):
    p = Drop({
        "id": 900001, "title": title, "handle": "amara-cane-sofa",
        "variants": variants,
        "metafields": Metafields({"custom": {
            k: (v if isinstance(v, Metafield) else mf(v)) for k, v in (product_custom or {}).items()
        }}),
    })
    p["selected_or_first_available_variant"] = variants[0]
    return p


def spec_settings(**over):
    base = {
        "source": "rows", "namespace": "custom", "json_key": "dimensions",
        "unavailable_text": "This size / colour combination is currently unavailable.",
        "debug": False,
    }
    for i in range(1, 7):
        base[f"row_{i}_enabled"] = False
        for k in ("label", "key", "fallback", "size_map"):
            base[f"row_{i}_{k}"] = None
    base.update(over)
    return Drop(base)


DIM_SETTINGS = spec_settings(
    heading="Dimensions", note="All dimensions in inches · measured by hand, ±½ in", columns=4,
    row_1_enabled=True, row_1_label="Width", row_1_key="width",
    row_2_enabled=True, row_2_label="Depth", row_2_key="depth",
    row_3_enabled=True, row_3_label="Height", row_3_key="height",
    row_4_enabled=True, row_4_label="Seat height", row_4_key="seat_height",
    row_5_enabled=True, row_5_label="Weight", row_5_key="weight",
)
MAT_SETTINGS = spec_settings(
    heading="Material & Care", note=None,
    row_1_enabled=True, row_1_label="Material", row_1_key="material",
    row_2_enabled=True, row_2_label="Finish", row_2_key="finish",
    row_3_enabled=True, row_3_label="Care", row_3_key="care",
)


def render_blocks(prod, dim_settings, mat_settings, id_prefix, section_id, design_mode=False):
    block = Drop({"id": id_prefix, "shopify_attributes": f'id="shopify-block-{id_prefix}" class="shopify-block"'})
    dims = R.render_file("dews-spec-block", {
        "product": prod, "block": block, "settings": dim_settings, "layout": "tiles",
        "element_id": f"DewsDimensions-{section_id}", "section_id": section_id,
        "request": Drop({"design_mode": design_mode}),
    })
    mats = R.render_file("dews-spec-block", {
        "product": prod, "block": block, "settings": mat_settings, "layout": "rows",
        "element_id": f"DewsMaterials-{section_id}", "section_id": section_id,
        "request": Drop({"design_mode": design_mode}),
    })
    return dims + "\n" + mats


# ============================================================ SCENARIO A
# Correct setup: every size variant carries its OWN metafields.
A = make_product([
    variant(4001, "1 Seater", {"width": "38 in", "depth": "34 in", "height": "31 in",
                               "seat_height": "18 in", "weight": "42 lb",
                               "material": "Sheesham wood + hand-woven cane",
                               "finish": "Natural lacquer",
                               "care": mf("Wipe with a dry, soft cloth.\nKeep out of direct sunlight.\nRe-oil once a year.", "multi_line_text_field")}, 24999),
    variant(4002, "2 Seater", {"width": "58 in", "depth": "34 in", "height": "31 in",
                               "seat_height": "18 in", "weight": "68 lb",
                               "material": "Sheesham wood + hand-woven cane",
                               "finish": "Natural lacquer",
                               "care": mf("Wipe with a dry, soft cloth.\nKeep out of direct sunlight.\nRe-oil once a year.", "multi_line_text_field")}, 38999),
    variant(4003, "3 Seater", {"width": "78 in", "depth": "34 in", "height": "31 in",
                               "seat_height": "18 in", "weight": "94 lb",
                               "material": "Sheesham wood + hand-woven cane",
                               "finish": "Natural lacquer",
                               "care": mf("Wipe with a dry, soft cloth.\nKeep out of direct sunlight.\nRe-oil once a year.", "multi_line_text_field")}, 52999),
])
A_DIM = render_blocks(A, DIM_SETTINGS, MAT_SETTINGS, "dimensions_a", "secA")

# ============================================================ SCENARIO B
# The old bug: definitions live on the PRODUCT, not the variants.
B = make_product(
    [variant(5001, "1 Seater", {}, 24999), variant(5002, "2 Seater", {}, 38999), variant(5003, "3 Seater", {}, 52999)],
    product_custom={"width": "58 in", "depth": "34 in", "height": "31 in", "seat_height": "18 in", "weight": "68 lb",
                    "material": "Sheesham wood + hand-woven cane", "finish": "Natural lacquer",
                    "care": mf("Wipe with a dry, soft cloth.\nKeep out of direct sunlight.", "multi_line_text_field")},
)
B_DIM = render_blocks(B, DIM_SETTINGS, MAT_SETTINGS, "dimensions_b", "secB")

# ============================================================ SCENARIO C
# No metafields at all — the per-size fallback map in the block settings.
C = make_product([variant(6001, "1 Seater", {}, 24999), variant(6002, "2 Seater", {}, 38999), variant(6003, "3 Seater", {}, 52999)])
C_DIM = render_blocks(C, spec_settings(
    heading="Dimensions", note="Driven purely by the per-size map in the block settings", columns=4,
    row_1_enabled=True, row_1_label="Width", row_1_key="width",
    row_1_size_map="1 Seater: 38 in\n2 Seater: 58 in\n3 Seater: 78 in",
    row_2_enabled=True, row_2_label="Depth", row_2_key="depth", row_2_fallback="34 in",
    row_3_enabled=True, row_3_label="Height", row_3_key="height", row_3_fallback="31 in",
    row_4_enabled=True, row_4_label="Seat height", row_4_key="seat_height", row_4_fallback="18 in",
    row_5_enabled=True, row_5_label="Weight", row_5_key="weight",
    row_5_size_map="1 Seater: 42 lb\n2 Seater: 68 lb\n3 Seater: 94 lb",
), MAT_SETTINGS, "dimensions_c", "secC")

# ---- one variant with a MISSING metafield, to show rows hiding -------------
D = make_product([
    variant(7001, "1 Seater", {"width": "38 in", "depth": "34 in", "height": "31 in", "seat_height": "18 in", "weight": "42 lb",
                               "material": "Sheesham wood", "finish": "Natural lacquer"}, 24999),
    variant(7002, "2 Seater", {"width": "58 in", "depth": "34 in", "height": "31 in",
                               "material": "Sheesham wood", "finish": "Walnut stain"}, 38999),   # no seat_height / weight
])
D_DIM = render_blocks(D, DIM_SETTINGS, MAT_SETTINGS, "dimensions_d", "secD")

# ============================================================ assemble page
def read(p):
    return open(os.path.join(ROOT, p), encoding="utf-8").read()


css = read("assets/component-dews-product.css")
constants = read("assets/constants.js")
pubsub = read("assets/pubsub.js")
pdp = read("assets/dews-pdp.js")

SCENARIOS = [
    ("A", "Variant metafields ✅", "The correct setup. Every size has its own <code>custom.width</code>, <code>custom.depth</code>… on the <b>variant</b>.",
     A_DIM, A, "secA"),
    ("B", "Product metafield only ⚠️", "The old bug at data level. Definitions sit on the <b>product</b>, so every size inherits one value and nothing can differ.",
     B_DIM, B, "secB"),
    ("C", "Per-size fallback map ✅", "No metafields at all. Values come from the block's <i>Per-option fallback map</i> setting — still size-specific.",
     C_DIM, C, "secC"),
    ("D", "Some metafields missing", "2 Seater has no <code>seat_height</code> / <code>weight</code>. Those tiles hide themselves for that size only.",
     D_DIM, D, "secD"),
]


def pills(prod, section_id):
    out = [f'<variant-selects id="variant-selects-{section_id}" data-section="{section_id}" '
           f'data-product-id="{prod["id"]}" data-product-handle="{prod["handle"]}" '
           f'data-product-title="{prod["title"]}" data-currency-code="INR">',
           '<fieldset class="js product-form__input product-form__input--pill">',
           '<legend class="form__label">Size <span style="font-weight:400;color:var(--dews-muted)">- '
           '<span data-selected-value>' + prod["variants"][0]["title"] + '</span></span></legend>',
           '<div class="pill-row">']
    for i, v in enumerate(prod["variants"]):
        out.append(
            f'<label class="pill"><input type="radio" name="options[Size]-{section_id}" '
            f'value="{v["title"]}" data-variant-id="{v["id"]}" data-price="{v["price"]}"'
            f'{" checked" if i == 0 else ""}><span>{v["title"]}</span></label>')
    out.append(f'<label class="pill pill--unavailable"><input type="radio" name="options[Size]-{section_id}" '
               f'value="__none__" data-variant-id="" data-price=""><span>3 Seater · Bouclé (unavailable)</span></label>')
    out += ['</div></fieldset></variant-selects>']
    return "\n".join(out)


def scenario_html(key, title, blurb, blocks, prod, sid):
    v0 = prod["variants"][0]
    return f"""
    <section class="demo-card" data-demo="{key}">
      <header class="demo-card__head">
        <h2><span class="demo-badge">{key}</span> {title}</h2>
        <p>{blurb}</p>
      </header>

      <div class="dews-product demo-card__body">
        <div class="demo-info">
          <product-info id="MainProduct-{sid}" class="section-{sid}-padding dews-product"
                        data-section="{sid}" data-product-id="{prod['id']}"
                        data-update-url="true" data-url="/products/{prod['handle']}">
            <p class="product__text">DEW'S FURNITURE</p>
            <div class="product__title"><h1>{prod['title']}</h1></div>

            <div class="price" id="price-{sid}">
              <span class="price__regular">₹<span data-price-amount>{v0['price']:,}</span></span>
            </div>

            {pills(prod, sid)}

            {blocks}

            <product-form>
              <form id="product-form-{sid}">
                <input type="hidden" name="id" value="{v0['id']}">
                <div class="demo-buyrow">
                  <button type="submit" class="product-form__submit" name="add">Add to cart</button>
                </div>
              </form>
            </product-form>
          </product-info>
        </div>
      </div>
    </section>"""


cards = "\n".join(scenario_html(*s) for s in SCENARIOS)

PAGE = f"""<!doctype html>
<!--
  GENERATED FILE — do not edit by hand.
  Regenerate with:  python3 tools/preview/build.py

  Contains the real rendered output of snippets/dews-spec-block.liquid plus the
  real assets/dews-pdp.js, assets/constants.js, assets/pubsub.js and
  assets/component-dews-product.css, all inlined so this one file can be opened
  straight from a browser or served statically.
-->
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Dew's Furniture — variant-aware Dimensions block (live demo)</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@300;400;500;600;700;800&family=Instrument+Serif:ital@0;1&display=swap">
<style>
/* ---- Dawn-ish base so component-dews-product.css has what it needs ---- */
:root {{ --dews-paper:#fbfaf8; --dews-line:#e2dcd3; }}
*,*::before,*::after {{ box-sizing:border-box; }}
body {{ margin:0; background:#f6f3ee; color:#1c1a17;
       font-family:'Archivo',system-ui,sans-serif; font-size:16px; line-height:1.5;
       -webkit-font-smoothing:antialiased; }}
.wrap {{ max-width:1100px; margin:0 auto; padding:2.5rem 1.25rem 4rem; }}
product-info, variant-selects, product-form, product-component, dews-variant-info {{ display:block; }}
.page-head h1 {{ font-family:'Instrument Serif',serif; font-size:2.4rem; font-weight:400; margin:0 0 .35rem; }}
.page-head p {{ color:#6c6459; margin:0 0 .4rem; max-width:70ch; }}
.page-head code {{ background:#ece7dd; padding:.1rem .35rem; border-radius:4px; font-size:.85em; }}
.legend {{ display:flex; flex-wrap:wrap; gap:.5rem; margin:1.1rem 0 2rem; }}
.legend span {{ font-size:.72rem; font-weight:600; padding:.3rem .6rem; border-radius:999px;
                background:#fff; border:1px solid var(--dews-line); color:#6c6459; }}

.demo-card {{ background:#fff; border:1px solid var(--dews-line); border-radius:14px;
              margin-bottom:1.75rem; overflow:hidden; box-shadow:0 1px 2px rgba(28,26,23,.04); }}
.demo-card__head {{ padding:1.1rem 1.4rem; border-bottom:1px solid var(--dews-line); background:#fbfaf8; }}
.demo-card__head h2 {{ margin:0 0 .3rem; font-size:1.02rem; font-weight:700; display:flex; align-items:center; gap:.55rem; }}
.demo-card__head p {{ margin:0; font-size:.82rem; color:#6c6459; max-width:88ch; }}
.demo-card__head code {{ background:#ece7dd; padding:.05rem .3rem; border-radius:4px; font-size:.9em; }}
.demo-badge {{ display:inline-grid; place-items:center; width:1.55rem; height:1.55rem; border-radius:7px;
               background:#c1502e; color:#fff; font-size:.78rem; font-weight:800; }}
.demo-card__body {{ padding:1.4rem; }}

.product__text {{ font-size:.72rem; font-weight:600; letter-spacing:.09em; text-transform:uppercase; color:#7a746a; margin:0 0 .4rem; }}
.product__title h1 {{ font-size:1.5rem; font-weight:700; margin:0 0 .5rem; }}
.price {{ font-size:1.15rem; font-weight:700; margin-bottom:1.1rem; }}
.form__label {{ font-size:.78rem; font-weight:700; letter-spacing:.03em; text-transform:uppercase;
                color:#3a352f; margin-bottom:.55rem; }}
.pill-row {{ display:flex; flex-wrap:wrap; gap:.45rem; }}
.pill input {{ position:absolute; opacity:0; pointer-events:none; }}
.pill span {{ display:inline-block; padding:.5rem .95rem; border:1px solid var(--dews-line);
              border-radius:999px; font-size:.82rem; font-weight:600; cursor:pointer;
              background:#fff; transition:all .16s ease; }}
.pill span:hover {{ border-color:#c9bfae; }}
.pill input:checked + span {{ background:#1c1a17; border-color:#1c1a17; color:#fff; }}
.pill input:focus-visible + span {{ outline:2px solid #c1502e; outline-offset:2px; }}
.pill--unavailable span {{ color:#a8a096; border-style:dashed; }}
.pill--unavailable input:checked + span {{ background:#efeae2; border-color:#d8d0c4; color:#8c8378; }}
.demo-buyrow {{ margin-top:1.25rem; }}
.product-form__submit {{ height:3rem; padding:0 1.6rem; border:0; border-radius:999px; background:#1c1a17;
                         color:#fff; font-family:inherit; font-size:.88rem; font-weight:700; cursor:pointer; }}
.product-form__submit:hover {{ background:#c1502e; }}

.log {{ margin-top:1.6rem; background:#1c1a17; color:#e8e2d8; border-radius:12px; padding:1rem 1.2rem;
        font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:.74rem; line-height:1.7; }}
.log h3 {{ margin:0 0 .5rem; font-size:.72rem; letter-spacing:.1em; text-transform:uppercase; color:#a89e90; font-family:'Archivo',sans-serif; }}
.log div {{ white-space:pre-wrap; }}
.log .ok {{ color:#8fd69f; }}
.log .warn {{ color:#f0c674; }}
.log .dim {{ color:#8b8378; }}
</style>
<style>
{css}
</style>
</head>
<body>
<div class="wrap">
  <div class="page-head">
    <h1>Variant-aware Dimensions &amp; Material blocks</h1>
    <p>
      Yeh page <b>real</b> cheezein use karta hai — markup <code>snippets/dews-spec-block.liquid</code> se render hua hai,
      behaviour <code>assets/dews-pdp.js</code> se aata hai, aur event bus Dawn ke asli
      <code>constants.js</code> + <code>pubsub.js</code> hain. Sirf <code>product-info.js</code> mock hai
      (wohi do kaam karta hai jo Dawn fetch ke baad karta hai).
    </p>
    <p><b>Size pills pe click karo</b> — dimensions turant badalne chahiye. Neeche event log bhi hai.</p>
    <div class="legend">
      <span>Click a size pill</span><span>Values swap with no page reload</span>
      <span>Rows with no value hide themselves</span><span>Try the dashed “unavailable” pill too</span>
    </div>
  </div>

  {cards}

  <div class="log" id="log"><h3>Event log</h3><div id="log-body"></div></div>
</div>

<script>{constants}</script>
<script>{pubsub}</script>
<script>{pdp}</script>
<script>
/* ==========================================================================
   Mock of Dawn's product-info.js — only the parts that matter here:
     updateVariantInputs(variant?.id)   -> input[name="id"].value + change event
     publish(variantChange, {{sectionId, html, variant}})
   Nothing else is faked.
   ========================================================================== */
(function () {{
  var logBody = document.getElementById('log-body');
  function log(msg, cls) {{
    var d = document.createElement('div');
    if (cls) d.className = cls;
    d.textContent = msg;
    logBody.insertBefore(d, logBody.firstChild);
    while (logBody.childNodes.length > 22) logBody.removeChild(logBody.lastChild);
  }}

  document.querySelectorAll('variant-selects').forEach(function (picker) {{
    var sectionId = picker.dataset.section;
    var productInfo = picker.closest('product-info');
    var input = productInfo.querySelector('input[name="id"]');
    var priceEl = productInfo.querySelector('[data-price-amount]');
    var selectedValue = picker.querySelector('[data-selected-value]');

    picker.addEventListener('change', function (e) {{
      var radio = e.target;
      if (radio.type !== 'radio') return;

      var variantId = radio.dataset.variantId || '';
      if (selectedValue) selectedValue.textContent = radio.value;

      // --- exactly what Dawn does once its section fetch resolves ---
      input.value = variantId;
      input.dispatchEvent(new Event('change', {{ bubbles: true }}));

      if (!variantId) {{
        log('[' + sectionId + '] no matching variant -> setUnavailable() (Dawn skips the pubsub event here)', 'warn');
        return;
      }}

      publish(PUB_SUB_EVENTS.variantChange, {{
        data: {{ sectionId: sectionId, html: null, variant: {{ id: Number(variantId), title: radio.value }} }}
      }});

      if (priceEl) {{
        priceEl.textContent = radio.dataset.price
          ? Number(radio.dataset.price).toLocaleString('en-IN')
          : '\u2014';
      }}

      var dims = productInfo.querySelector('[data-dim-key="width"] [data-dim-val]');
      log('[' + sectionId + '] variantChange -> ' + radio.value +
          (dims ? '   Width now: ' + (dims.textContent.trim() || '(hidden)') : ''), 'ok');
    }});
  }});

  // Report the actual custom element wiring once, at startup.
  document.querySelectorAll('dews-variant-info').forEach(function (el) {{
    el.addEventListener('dews:spec-updated', function (ev) {{
      log('  ↳ ' + el.id + ' repainted from ' + ev.detail.source + ' data (variant ' + ev.detail.variantId + ')', 'dim');
    }});
  }});
  log('ready — ' + document.querySelectorAll('dews-variant-info').length +
      ' spec block(s) wired to Dawn pubsub', 'ok');
}})();
</script>
</body>
</html>
"""

out_dir = os.path.join(ROOT, "tools", "preview")
os.makedirs(out_dir, exist_ok=True)
out = os.path.join(out_dir, "index.html")
open(out, "w", encoding="utf-8").write(PAGE)

# sanity: every scenario must have produced valid embedded JSON
import re  # noqa: E402
found = re.findall(r'<script type="application/json" data-dews-spec-json>(.*?)</script>', PAGE, re.DOTALL)
for i, blob in enumerate(found, 1):
    json.loads(blob)
print(f"✓ wrote {os.path.relpath(out, ROOT)}  ({len(PAGE)//1024} KB)")
print(f"✓ {len(found)} embedded JSON payloads, all valid")
