/* ==========================================================================
   Dew's PDP — dynamic product info
   - Dimensions block: per-variant values ship as JSON; on variant change
     the visible values swap without a reload.
   - Material & Care block: same pattern (material/finish/care).
   - Safe no-ops when the blocks/markup aren't on the page.
   ========================================================================== */
(function () {
  'use strict';

  /* Dimensions: swap visible values for the newly selected variant. */
  function updateDimensions(variantId) {
    if (!variantId) return;
    var roots = document.querySelectorAll('[data-dews-dims]');
    if (!roots.length) return;
    roots.forEach(function (root) {
      var jsonEl = root.querySelector('[data-dews-dims-json]');
      if (!jsonEl) return;
      var map = null;
      try {
        map = JSON.parse(jsonEl.textContent);
      } catch (e) {
        return;
      }
      var dims = map && map[String(variantId)];
      if (!dims) return;
      Object.keys(dims).forEach(function (key) {
        var li = root.querySelector('[data-dim="' + key + '"]');
        if (!li) return;
        var val = dims[key];
        if (val) {
          li.hidden = false;
          var out = li.querySelector('[data-dim-val]');
          if (out) out.textContent = val;
        } else {
          li.hidden = true;
        }
      });
    });
  }

  /* Material & Care: swap visible values for the newly selected variant. */
  function updateMaterials(variantId) {
    if (!variantId) return;
    var roots = document.querySelectorAll('[data-dews-mat]');
    if (!roots.length) return;
    roots.forEach(function (root) {
      var jsonEl = root.querySelector('[data-dews-mat-json]');
      if (!jsonEl) return;
      var map = null;
      try {
        map = JSON.parse(jsonEl.textContent);
      } catch (e) {
        return;
      }
      var fields = map && map[String(variantId)];
      if (!fields) return;
      Object.keys(fields).forEach(function (key) {
        var wrap = root.querySelector('[data-mat="' + key + '"]');
        if (!wrap) return;
        var val = fields[key];
        if (val) {
          wrap.hidden = false;
          var out = wrap.querySelector('[data-mat-val]');
          if (out) {
            if (key === 'care') {
              /* multi-line: rebuild with <br> using safe text nodes */
              out.textContent = '';
              String(val)
                .split('\n')
                .forEach(function (line, i) {
                  if (i) out.appendChild(document.createElement('br'));
                  out.appendChild(document.createTextNode(line));
                });
            } else {
              out.textContent = val;
            }
          }
        } else {
          wrap.hidden = true;
        }
      });
    });
  }

  function updateAll(variantId) {
    updateDimensions(variantId);
    updateMaterials(variantId);
  }

  /* Primary path: Dawn's own pubsub event (payload: event.data.variant). */
  try {
    if (typeof subscribe === 'function' && typeof PUB_SUB_EVENTS !== 'undefined' && PUB_SUB_EVENTS.variantChange) {
      subscribe(PUB_SUB_EVENTS.variantChange, function (event) {
        var v = event && event.data && event.data.variant;
        if (v && v.id) updateAll(v.id);
      });
    }
  } catch (e) {
    /* pubsub unavailable — fallback below still handles it */
  }

  /* Fallback path: variant picker change events (bubble after Dawn updates). */
  document.addEventListener('change', function (e) {
    var picker = e.target && e.target.closest ? e.target.closest('variant-selects, variant-radios') : null;
    if (!picker) return;
    var scope = picker.closest('product-info') || document;
    var idInput = scope.querySelector('input[name="id"]');
    if (idInput && idInput.value) updateAll(idInput.value);
  });
})();
