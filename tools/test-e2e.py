#!/usr/bin/env python3
"""
END-TO-END test: real Liquid -> real browser JS.

1. Renders snippets/dews-spec-block.liquid with the minimal Liquid engine in
   tools/liquid_render.py, using a 3-size sofa whose variants each carry their
   OWN custom.width metafield.
2. Drops that exact HTML into a jsdom page shaped like Dawn's PDP.
3. Loads assets/dews-pdp.js and simulates a shopper clicking "2 Seater"
   (Dawn's pubsub event AND the product form input change).
4. Asserts the on-screen Width actually changes from 38 in to 58 in.

Run: python3 tools/test-e2e.py
"""
import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from liquid_render import Drop, Metafield, Metafields, Renderer  # noqa: E402

R = Renderer([os.path.join(ROOT, "snippets")])


def variant(vid, title, custom):
    return Drop({
        "id": vid, "title": title, "options": [title],
        "metafields": Metafields({"custom": {k: Metafield(v) for k, v in custom.items()}}),
    })


SOFA = Drop({
    "id": 900001,
    "title": "Sheesham Wood Sofa",
    "handle": "sheesham-wood-sofa",
    "variants": [
        variant(4001, "1 Seater", {"width": "38 in", "depth": "34 in", "height": "31 in", "seat_height": "18 in"}),
        variant(4002, "2 Seater", {"width": "58 in", "depth": "34 in", "height": "31 in", "seat_height": "18 in"}),
        variant(4003, "3 Seater", {"width": "78 in", "depth": "34 in", "height": "31 in", "seat_height": "18 in"}),
    ],
    "metafields": Metafields({"custom": {}}),
})
SOFA["selected_or_first_available_variant"] = SOFA["variants"][0]

SETTINGS = Drop({
    "heading": "Dimensions", "note": "All dimensions in inches", "columns": 4,
    "source": "rows", "namespace": "custom", "json_key": "dimensions",
    "unavailable_text": "This combination is currently unavailable.", "debug": False,
    "row_1_enabled": True, "row_1_label": "Width", "row_1_key": "width",
    "row_1_fallback": None, "row_1_size_map": None,
    "row_2_enabled": True, "row_2_label": "Depth", "row_2_key": "depth",
    "row_2_fallback": None, "row_2_size_map": None,
    "row_3_enabled": True, "row_3_label": "Height", "row_3_key": "height",
    "row_3_fallback": None, "row_3_size_map": None,
    "row_4_enabled": True, "row_4_label": "Seat height", "row_4_key": "seat_height",
    "row_4_fallback": None, "row_4_size_map": None,
    "row_5_enabled": False, "row_6_enabled": False,
})

block_html = R.render_file("dews-spec-block", {
    "product": SOFA,
    "block": Drop({"id": "dimensions_dews", "shopify_attributes": 'id="shopify-block-dimensions_dews" class="shopify-block"'}),
    "settings": SETTINGS,
    "layout": "tiles",
    "element_id": "DewsDimensions-main",
    "section_id": "main",
    "request": Drop({"design_mode": False}),
})

# --- sanity: the Liquid output must be usable on its own --------------------
import re  # noqa: E402
m = re.search(r'<script type="application/json" data-dews-spec-json>(.*?)</script>', block_html, re.DOTALL)
assert m, "no embedded JSON in the rendered block"
parsed = json.loads(m.group(1))
assert parsed["byRow"]["width"]["4002"] == "58 in", parsed
print("✓ Liquid rendered valid, per-variant JSON:")
print("   " + json.dumps(parsed["byRow"]["width"]))

PAGE = """<!doctype html><html><head>
<meta charset="utf-8">
</head><body>
<product-info id="MainProduct-main" class="dews-product" data-section="main" data-product-id="900001"
              data-update-url="true" data-url="/products/sheesham-wood-sofa">
  <div class="product__info-container">
    <variant-selects id="variant-selects-main" data-section="main" data-product-id="900001">
      <fieldset class="product-form__input product-form__input--pill">
        <legend class="form__label">Size - <span data-selected-value>1 Seater</span></legend>
        <label><input type="radio" name="options[Size]" value="1 Seater" data-option-value-id="ov1" checked></label>
        <label><input type="radio" name="options[Size]" value="2 Seater" data-option-value-id="ov2"></label>
        <label><input type="radio" name="options[Size]" value="3 Seater" data-option-value-id="ov3"></label>
      </fieldset>
    </variant-selects>

    __BLOCK__

    <product-form>
      <form id="product-form-main">
        <input type="hidden" name="id" value="4001">
        <button type="submit" name="add">Add to cart</button>
      </form>
    </product-form>
  </div>
</product-info>
</body></html>""".replace("__BLOCK__", block_html)

tmp = tempfile.mkdtemp(prefix="dews-e2e-")
html_path = os.path.join(tmp, "pdp.html")
open(html_path, "w", encoding="utf-8").write(PAGE)

runner = os.path.join(tmp, "run.js")
RUNNER = r"""
const fs = require('fs');
const path = require('path');
let jsdomPath;
try { require.resolve('jsdom'); jsdomPath = 'jsdom'; }
catch (e) { jsdomPath = '/tmp/dewstest/node_modules/jsdom'; }
const { JSDOM, VirtualConsole } = require(jsdomPath);

const REPO = process.argv[2];
const PAGE = process.argv[3];

const PUBSUB = `
  const PUB_SUB_EVENTS = {
    cartUpdate:'cart-update', quantityUpdate:'quantity-update',
    optionValueSelectionChange:'option-value-selection-change',
    variantChange:'variant-change', cartError:'cart-error'
  };
  let subscribers = {};
  function subscribe(n, cb){ (subscribers[n] = subscribers[n]||[]).push(cb);
    return function(){ subscribers[n] = subscribers[n].filter(function(x){return x!==cb;}); }; }
  function publish(n, d){ if(subscribers[n]) return Promise.all(subscribers[n].map(function(cb){return cb(d);})); return Promise.resolve(); }
`;

const pageErrors = [];
const vc = new VirtualConsole();
vc.on('jsdomError', (e) => pageErrors.push('jsdomError: ' + e.message));
vc.on('error', (...a) => pageErrors.push('console.error: ' + a.join(' ')));

const dom = new JSDOM(fs.readFileSync(PAGE, 'utf8'), {
  runScripts: 'dangerously', pretendToBeVisual: true, virtualConsole: vc,
});
const win = dom.window;

function addScript(code) {
  const s = win.document.createElement('script');
  s.textContent = code;
  win.document.body.appendChild(s);
}
addScript(PUBSUB);                                              // constants.js + pubsub.js
addScript(fs.readFileSync(path.join(REPO, 'assets/dews-pdp.js'), 'utf8'));

let pass = 0, fail = 0;
function eq(actual, expected, label) {
  if (actual === expected) { pass++; console.log('  \u2713 ' + label); }
  else { fail++; console.log('  \u2717 ' + label + '   (got ' + JSON.stringify(actual) + ', want ' + JSON.stringify(expected) + ')'); }
}

function width() {
  const row = win.document.querySelector('[data-dim-key="width"]');
  return row.hidden ? null : row.querySelector('[data-dim-val]').textContent.trim();
}
function seat() {
  const row = win.document.querySelector('[data-dim-key="seat_height"]');
  return row.hidden ? null : row.querySelector('[data-dim-val]').textContent.trim();
}
function pick(size) {                       // shopper clicks a size pill
  const radio = win.document.querySelector('input[value="' + size + '"]');
  radio.checked = true;
  radio.dispatchEvent(new win.Event('change', { bubbles: true }));
}
function dawnFetchDone(variantId, sectionHtml) {
  // what product-info.js does after its section fetch:
  //   updateVariantInputs(variant.id) -> input change
  //   publish(variantChange, {sectionId, html, variant})
  const input = win.document.querySelector('input[name="id"]');
  input.value = variantId === null ? '' : String(variantId);
  input.dispatchEvent(new win.Event('change', { bubbles: true }));
  if (variantId !== null) {
    win.__payload = { data: { sectionId: 'main', html: sectionHtml || null,
      variant: { id: variantId, title: 'v' + variantId } } };
    addScript('publish(PUB_SUB_EVENTS.variantChange, window.__payload);');
  }
}

console.log('\nEND-TO-END: Liquid-rendered markup + real dews-pdp.js in jsdom');
console.log('———————————————————————————————————————————————————————————————');
eq(width(), '38 in', 'page load shows the 1 Seater width (server-rendered)');
eq(seat(),  '18 in', 'page load shows the 1 Seater seat height');

dawnFetchDone(4002);
eq(width(), '58 in', 'clicking 2 Seater changes Width to 58 in  <<< the reported bug');

dawnFetchDone(4003);
eq(width(), '78 in', 'clicking 3 Seater changes Width to 78 in');

dawnFetchDone(4001);
eq(width(), '38 in', 'clicking back to 1 Seater restores 38 in');

dawnFetchDone(null);
eq(win.document.querySelector('dews-variant-info').classList.contains('is-unavailable'), true,
   'unavailable combination is flagged');
eq(win.document.querySelector('[data-dews-unavailable]').hidden, false, 'unavailable message shown');

dawnFetchDone(4003);
eq(win.document.querySelector('dews-variant-info').classList.contains('is-unavailable'), false,
   'flag cleared once a real variant is back');
eq(width(), '78 in', 'values correct again after recovery');

eq(pageErrors.length, 0, 'no JS errors were logged during the whole flow' +
   (pageErrors.length ? ': ' + pageErrors.join(' | ') : ''));

console.log('\n' + pass + '/' + (pass + fail) + ' end-to-end checks passed');
process.exit(fail ? 1 : 0);
"""
open(runner, "w", encoding="utf-8").write(RUNNER)

print("\n→ running jsdom end-to-end …")
res = subprocess.run(["node", runner, ROOT, html_path], capture_output=True, text=True)
print(res.stdout)
if res.stderr.strip():
    print("STDERR:", res.stderr[-2000:])
sys.exit(res.returncode)
