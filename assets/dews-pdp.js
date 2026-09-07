/* ==========================================================================
   Dew's PDP — dynamic product info
   - Dimensions block: per-variant values ship as JSON; on variant change
     the visible values swap without a reload.
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

  /* Primary path: Dawn's own pubsub event (payload: event.data.variant). */
  try {
    if (typeof subscribe === 'function' && typeof PUB_SUB_EVENTS !== 'undefined' && PUB_SUB_EVENTS.variantChange) {
      subscribe(PUB_SUB_EVENTS.variantChange, function (event) {
        var v = event && event.data && event.data.variant;
        if (v && v.id) updateDimensions(v.id);
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
    if (idInput && idInput.value) updateDimensions(idInput.value);
  });
})();
