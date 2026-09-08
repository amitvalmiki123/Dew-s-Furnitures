/**
 * Integration test for assets/dews-pdp.js
 *
 * Builds a jsdom page that mimics Dawn's PDP (product-info + product form +
 * the <dews-variant-info> spec block), loads the real Dawn pubsub shim and the
 * real dews-pdp.js, then simulates variant changes exactly the way Dawn does.
 *
 * Run: node tools/test-dews-pdp.js
 */
const fs = require('fs');
const path = require('path');

let JSDOM;
try {
  ({ JSDOM } = require('jsdom'));
} catch (e) {
  ({ JSDOM } = require('/tmp/dewstest/node_modules/jsdom'));
}

const SRC = fs.readFileSync(path.join(__dirname, '..', 'assets', 'dews-pdp.js'), 'utf8');

// jsdom's custom-elements support is partial: `window.customElements` exists, so
// the real dews-pdp.js calls define() and jsdom then throws from inside its own
// internals, dumping a stack trace to stderr. The harness already handles that
// path (it falls back to instantiating the class directly), so swallow just that
// one expected error instead of alarming whoever reads the test output.
const { VirtualConsole } = (() => {
  try { return require('jsdom'); } catch (e) { return require('/tmp/dewstest/node_modules/jsdom'); }
})();

function quietConsole() {
  const vc = new VirtualConsole();
  vc.on('error', (msg, detail) => {
    const text = String(msg) + String((detail && detail.stack) || '');
    if (/customElements|CustomElementRegistry|custom element/i.test(text)) return;
    console.error('[jsdom]', msg);
  });
  vc.on('jsdomError', (err) => {
    const text = String(err && (err.message || '')) + String((err && err.stack) || '');
    if (/customElements|CustomElementRegistry|custom element/i.test(text)) return;
    console.error('[jsdom]', err);
  });
  vc.on('warn', (...a) => console.warn(...a));
  vc.on('log', (...a) => console.log(...a));
  return vc;
}

let failures = 0;
let checks = 0;

function ok(condition, label) {
  checks++;
  if (condition) {
    console.log('  ✓ ' + label);
  } else {
    failures++;
    console.log('  ✗ ' + label);
  }
}

function eq(actual, expected, label) {
  ok(actual === expected, label + (actual === expected ? '' : `  (got ${JSON.stringify(actual)}, want ${JSON.stringify(expected)})`));
}

/* ------------------------------------------------------------------ *
 * Markup that mirrors what snippets/dews-spec-block.liquid emits
 * ------------------------------------------------------------------ */
function specBlockHtml({ id = 'DewsDimensions-main', sectionId = 'main', variantId = '4001', json, rows }) {
  const items = rows
    .map(
      (r) => `
      <li class="dews-spec__item" data-dim-key="${r.key}"${r.value ? '' : ' hidden'}>
        <span class="dews-spec__label">${r.label}</span>
        <strong class="dews-spec__val" data-dim-val>${r.value || ''}</strong>
      </li>`
    )
    .join('');

  return `
    <dews-variant-info id="${id}" class="dews-spec dews-spec--tiles" data-dews-spec="rows"
      data-variant-id="${variantId}" data-section-id="${sectionId}">
      <p class="dews-spec__heading" data-dews-heading>Dimensions</p>
      <ul class="dews-spec__list">${items}</ul>
      <p class="dews-spec__note" data-dews-note>All dimensions in inches</p>
      <p class="dews-spec__unavailable" data-dews-unavailable hidden>This combination is currently unavailable.</p>
      <script type="application/json" data-dews-spec-json>${json}</script>
    </dews-variant-info>`;
}

function pageHtml(specHtml) {
  return `<!doctype html><html><body>
    <product-info id="MainProduct-main" data-section="main" data-url="/products/sofa">
      <variant-selects id="variant-selects-main">
        <fieldset><input type="radio" name="options[Size]" value="1 Seater" checked></fieldset>
      </variant-selects>
      ${specHtml}
      <form id="product-form-main">
        <input type="hidden" name="id" value="4001">
      </form>
    </product-info>
  </body></html>`;
}

/* Dawn's pubsub.js + constants.js (verbatim semantics) */
const PUBSUB_SHIM = `
  const PUB_SUB_EVENTS = {
    cartUpdate: 'cart-update',
    quantityUpdate: 'quantity-update',
    optionValueSelectionChange: 'option-value-selection-change',
    variantChange: 'variant-change',
    cartError: 'cart-error',
  };
  let subscribers = {};
  function subscribe(eventName, callback) {
    if (subscribers[eventName] === undefined) subscribers[eventName] = [];
    subscribers[eventName] = [...subscribers[eventName], callback];
    return function unsubscribe() {
      subscribers[eventName] = subscribers[eventName].filter((cb) => cb !== callback);
    };
  }
  function publish(eventName, data) {
    if (subscribers[eventName]) return Promise.all(subscribers[eventName].map((cb) => cb(data)));
    return Promise.resolve();
  }
`;

function boot({ json, rows, variantId = '4001', id = 'DewsDimensions-main', sectionId = 'main' }) {
  // `runScripts: 'dangerously'` + real <script> nodes, so top-level `const`
  // lands in the shared global lexical scope exactly like a browser.
  // (win.eval() would scope let/const to the eval call and hide them.)
  const dom = new JSDOM(pageHtml(specBlockHtml({ id, sectionId, variantId, json, rows })), {
    runScripts: 'dangerously',
    pretendToBeVisual: true,
    virtualConsole: quietConsole(),
  });
  const win = dom.window;

  function addScript(code) {
    const s = win.document.createElement('script');
    s.textContent = code;
    win.document.body.appendChild(s);
  }

  addScript(PUBSUB_SHIM); // constants.js + pubsub.js semantics
  addScript(SRC); // the real assets/dews-pdp.js

  return {
    win,
    doc: win.document,
    el: win.document.getElementById(id),
    input: win.document.querySelector('input[name="id"]'),
    value(key) {
      const row = win.document.querySelector(`[data-dim-key="${key}"]`);
      if (!row) return undefined;
      return row.hidden ? null : row.querySelector('[data-dim-val]').textContent.trim();
    },
    publishVariantChange(variant, opts = {}) {
      win.__dewsPayload = {
        data: Object.assign({ sectionId, html: null, variant }, opts),
      };
      addScript('publish(PUB_SUB_EVENTS.variantChange, window.__dewsPayload);');
    },
    setFormVariant(vid) {
      // exactly what Dawn's product-info.updateVariantInputs() does
      this.input.value = vid === null ? '' : String(vid);
      this.input.dispatchEvent(new win.Event('change', { bubbles: true }));
    },
  };
}

/* ================================================================== */
console.log('\n— byRow map (Dimensions block, 3 sofa sizes) ———————————————');
{
  const rows = [
    { key: 'width', label: 'Width', value: '38 in' },
    { key: 'depth', label: 'Depth', value: '34 in' },
    { key: 'height', label: 'Height', value: '31 in' },
    { key: 'seat', label: 'Seat height', value: '' }, // no data -> hidden
  ];
  const json = JSON.stringify({
    byRow: {
      width: { 4001: '38 in', 4002: '58 in', 4003: '78 in' },
      depth: { 4001: '34 in', 4002: '34 in', 4003: '34 in' },
      height: { 4001: '31 in', 4002: '31 in', 4003: '31 in' },
      seat: { 4001: null, 4002: null, 4003: null },
    },
  });

  const t = boot({ json, rows });

  eq(t.value('width'), '38 in', 'server render shows 1 Seater width');
  eq(t.value('seat'), null, 'row with no value starts hidden');

  t.publishVariantChange({ id: 4002, title: '2 Seater' });
  eq(t.value('width'), '58 in', 'pubsub variantChange -> 2 Seater width');
  eq(t.el.dataset.variantId, '4002', 'data-variant-id tracked');

  t.publishVariantChange({ id: 4003, title: '3 Seater' });
  eq(t.value('width'), '78 in', 'pubsub variantChange -> 3 Seater width');

  t.setFormVariant(4001);
  eq(t.value('width'), '38 in', 'form input change -> back to 1 Seater');

  t.setFormVariant(null);
  ok(t.el.classList.contains('is-unavailable'), 'unavailable combination flagged');
  eq(t.doc.querySelector('[data-dews-unavailable]').hidden, false, 'unavailable note shown');

  t.setFormVariant(4002);
  ok(!t.el.classList.contains('is-unavailable'), 'available again clears the flag');
  eq(t.doc.querySelector('[data-dews-unavailable]').hidden, true, 'unavailable note hidden again');
  eq(t.value('width'), '58 in', 'value restored after unavailable');

  t.publishVariantChange({ id: 9999, title: 'Other product' });
  eq(t.value('width'), '58 in', 'variant from another product is ignored');
}

console.log('\n— row appears/disappears between variants —————————————————');
{
  const rows = [
    { key: 'width', label: 'Width', value: '38 in' },
    { key: 'arm', label: 'Arm height', value: '24 in' },
  ];
  const json = JSON.stringify({
    byRow: {
      width: { 4001: '38 in', 4002: '58 in' },
      arm: { 4001: '24 in', 4002: null }, // 2 Seater has no arm-height metafield
    },
  });
  const t = boot({ json, rows, variantId: '4001' });
  eq(t.value('arm'), '24 in', 'arm height visible for 1 Seater');
  t.publishVariantChange({ id: 4002 });
  eq(t.value('arm'), null, 'arm height hidden when the 2 Seater has no value');
  eq(t.value('width'), '58 in', 'width still updated');
  t.publishVariantChange({ id: 4001 });
  eq(t.value('arm'), '24 in', 'arm height comes back');
}

console.log('\n— byVariant map (JSON-metafield source mode) ————————————————');
{
  const rows = [
    { key: 'Width', label: 'Width', value: '38 in' },
    { key: 'Depth', label: 'Depth', value: '34 in' },
  ];
  const json = JSON.stringify({
    byVariant: {
      4001: { Width: '38 in', Depth: '34 in' },
      4002: { Width: '58 in', Depth: '36 in' },
    },
  });
  const t = boot({ json, rows, variantId: '4001' });
  t.publishVariantChange({ id: 4002 });
  eq(t.value('Width'), '58 in', 'byVariant shape resolves width');
  eq(t.value('Depth'), '36 in', 'byVariant shape resolves depth');
}

console.log('\n— values containing quotes / unicode / newlines —————————————');
{
  const rows = [{ key: 'care', label: 'Care', value: 'Wipe with a "dry" cloth' }];
  const json = JSON.stringify({
    byRow: { care: { 4001: 'Wipe with a "dry" cloth', 4002: 'Dust weekly\nAvoid direct sun — 30°C max' } },
  });
  const t = boot({ json, rows });
  t.publishVariantChange({ id: 4002 });
  eq(t.value('care'), 'Dust weekly\nAvoid direct sun — 30°C max', 'escaped + multi-line value survives JSON round-trip');
}

console.log('\n— server-rendered HTML from Dawn takes priority —————————————');
{
  const rows = [{ key: 'width', label: 'Width', value: '38 in' }];
  const json = JSON.stringify({ byRow: { width: { 4001: '38 in', 4002: '58 in' } } });
  const t = boot({ json, rows });

  // Dawn passes the parsed section response as `html`
  const fakeResponse = t.win.document.implementation.createHTMLDocument('resp');
  fakeResponse.body.innerHTML = specBlockHtml({
    json,
    rows: [{ key: 'width', label: 'Width', value: 'SIXTY (server)' }],
  });

  t.publishVariantChange({ id: 4002 }, { html: fakeResponse });
  eq(t.value('width'), 'SIXTY (server)', 'fresh Liquid output wins over the JSON map');
}

console.log('\n— malformed JSON must not throw or blank the block ——————————');
{
  const rows = [{ key: 'width', label: 'Width', value: '38 in' }];
  const t = boot({ json: '{"byRow": BROKEN', rows });
  eq(t.value('width'), '38 in', 'server-rendered value left untouched');
  let threw = false;
  try {
    t.publishVariantChange({ id: 4002 });
  } catch (e) {
    threw = true;
  }
  ok(!threw, 'no exception thrown');
  eq(t.value('width'), '38 in', 'value still intact after bad event');
}

console.log('\n— element removed from DOM unsubscribes (no leaks/errors) ———');
{
  const rows = [{ key: 'width', label: 'Width', value: '38 in' }];
  const json = JSON.stringify({ byRow: { width: { 4001: '38 in', 4002: '58 in' } } });
  const t = boot({ json, rows });
  t.el.remove();
  let threw = false;
  try {
    t.publishVariantChange({ id: 4002 });
  } catch (e) {
    threw = true;
  }
  ok(!threw, 'publishing after removal does not throw');
}

console.log(`\n${checks - failures}/${checks} checks passed`);
process.exit(failures ? 1 : 0);
