/* ==========================================================================
   Dew's Furniture — PDP variant-aware spec blocks
   ==========================================================================
   Powers the <dews-variant-info> element used by the "Dimensions" and
   "Material & Care" blocks in sections/main-product.liquid.

   Values are rendered server-side for the selected variant, and every other
   variant's values ship as JSON inside the element. This script swaps the
   visible values when the shopper picks a different size/colour.

   Three independent triggers, all of them fire AFTER Dawn has resolved the
   variant (so there is no race and no stale value):

     1. Dawn's pubsub `variantChange`  — carries the freshly rendered section
                                         HTML, so we can copy Liquid's own output.
     2. `change` on the product form's input[name="id"] — Dawn sets this value
                                         after its fetch; it is also the only
                                         signal for UNAVAILABLE combinations
                                         (Dawn skips the pubsub event then).
     3. Re-connect — when Dawn swaps the whole <product-info> (combined
                                         listing / product switch) a brand new
                                         element is created and syncs itself.

   Safe no-op when the element or its data are not on the page.
   ========================================================================== */
(function () {
  'use strict';

  if (window.customElements && window.customElements.get('dews-variant-info')) return;

  /* `PUB_SUB_EVENTS` is declared with `const` in constants.js, so it lives in
     the global lexical scope and is NOT a property of window. Reference it as
     a bare identifier behind a typeof guard. */
  var PUBSUB_OK = false;
  try {
    PUBSUB_OK = typeof subscribe === 'function' && typeof PUB_SUB_EVENTS !== 'undefined' && !!PUB_SUB_EVENTS.variantChange;
  } catch (err) {
    PUBSUB_OK = false;
  }

  function hasOwn(obj, key) {
    return !!obj && Object.prototype.hasOwnProperty.call(obj, key);
  }

  function parseJsonScript(el) {
    if (!el) return null;
    try {
      var data = JSON.parse(el.textContent || '');
      return data && typeof data === 'object' ? data : null;
    } catch (err) {
      if (window.console && console.warn) {
        console.warn("[Dew's] spec block: embedded JSON could not be parsed.", err);
      }
      return null;
    }
  }

  /* Supports both shapes the Liquid emits:
       { byRow:     { <rowKey>:    { <variantId>: value|null } } }
       { byVariant: { <variantId>: { <rowKey>:    value|null } } }        */
  function lookup(map, rowKey, variantId) {
    if (!map || !variantId) return undefined;
    var vid = String(variantId);

    if (hasOwn(map, 'byRow') && hasOwn(map.byRow, rowKey) && hasOwn(map.byRow[rowKey], vid)) {
      return map.byRow[rowKey][vid];
    }
    if (hasOwn(map, 'byVariant') && hasOwn(map.byVariant, vid) && hasOwn(map.byVariant[vid], rowKey)) {
      return map.byVariant[vid][rowKey];
    }
    return undefined;
  }

  function knowsVariant(map, variantId) {
    if (!map || !variantId) return false;
    var vid = String(variantId);
    if (hasOwn(map, 'byVariant')) return hasOwn(map.byVariant, vid);
    if (hasOwn(map, 'byRow')) {
      return Object.keys(map.byRow).some(function (rowKey) {
        return hasOwn(map.byRow[rowKey], vid);
      });
    }
    return false;
  }

  function escapeForSelector(value) {
    return String(value).replace(/\\/g, '\\\\').replace(/"/g, '\\"');
  }

  /* Brief highlight so it is obvious which values actually moved.
     Only called when a value really changed. */
  function flash(row) {
    if (!row.classList) return;
    row.classList.remove('is-updated');
    void row.offsetWidth; // restart the CSS animation
    row.classList.add('is-updated');
    window.setTimeout(function () {
      row.classList.remove('is-updated');
    }, 650);
  }

  class DewsVariantInfo extends HTMLElement {
    connectedCallback() {
      if (this.__dewsWired) {
        this.syncFromInput();
        return;
      }
      this.__dewsWired = true;

      this.__map = parseJsonScript(this.querySelector('[data-dews-spec-json]'));
      this.__rows = Array.prototype.slice.call(this.querySelectorAll('[data-dim-key]'));
      this.__unavailableEl = this.querySelector('[data-dews-unavailable]');

      var self = this;

      /* --- trigger 1: Dawn pubsub ------------------------------------- */
      if (PUBSUB_OK) {
        try {
          this.__unsubscribe = subscribe(PUB_SUB_EVENTS.variantChange, function (payload) {
            self.onVariantChange(payload);
          });
        } catch (err) {
          this.__unsubscribe = null;
        }
      }

      /* --- trigger 2: product form variant input ----------------------- */
      var scope = this.closest('product-info') || this.closest('product-component') || document;
      this.__input = scope.querySelector('input[name="id"]');
      if (this.__input) {
        this.__onInput = function () {
          self.syncFromInput();
        };
        this.__input.addEventListener('change', this.__onInput);
      }

      /* --- trigger 3: element (re)connected after a DOM swap ----------- */
      this.syncFromInput();
    }

    disconnectedCallback() {
      if (typeof this.__unsubscribe === 'function') {
        try {
          this.__unsubscribe();
        } catch (err) {
          /* already gone */
        }
      }
      this.__unsubscribe = null;

      if (this.__input && this.__onInput) {
        this.__input.removeEventListener('change', this.__onInput);
      }
      this.__input = null;
      this.__onInput = null;
      this.__rows = [];
      this.__map = null;
      this.__dewsWired = false;
    }

    /* Dawn publishes { data: { sectionId, html, variant } } */
    onVariantChange(payload) {
      var data = (payload && payload.data) || {};
      var variant = data.variant;

      if (!variant || !variant.id) {
        /* Unavailable combination. Only act when the event is clearly ours —
           the input listener covers this case for every other situation. */
        var sid = this.dataset.sectionId;
        if (sid && data.sectionId && sid === data.sectionId) this.setUnavailable(true);
        return;
      }

      var vid = String(variant.id);

      /* Ignore events from another product-info on the same page
         (e.g. a featured-product section). */
      if (!knowsVariant(this.__map, vid)) return;

      var fresh = null;
      if (data.html && this.id) {
        try {
          fresh = data.html.getElementById(this.id);
        } catch (err) {
          fresh = null;
        }
      }

      this.setUnavailable(false);
      this.render(vid, fresh);
    }

    syncFromInput() {
      if (!this.__input) return;
      var value = (this.__input.value || '').trim();

      if (!value) {
        this.setUnavailable(true);
        return;
      }
      if (value === this.dataset.variantId) {
        this.setUnavailable(false);
        return;
      }
      this.setUnavailable(false);
      this.render(value, null);
    }

    setUnavailable(on) {
      this.classList.toggle('is-unavailable', !!on);
      if (this.__unavailableEl) this.__unavailableEl.hidden = !on;
    }

    /* Paint every row for the given variant.
       `freshRoot` (optional) is the server-rendered copy of this same element
       from Dawn's section response — its output always wins. */
    render(variantId, freshRoot) {
      var map = this.__map;

      this.__rows.forEach(function (row) {
        var key = row.getAttribute('data-dim-key');
        var out = row.querySelector('[data-dim-val]');
        if (!key || !out) return;

        var value = null;
        var resolved = false;

        if (freshRoot) {
          var freshRow = freshRoot.querySelector('[data-dim-key="' + escapeForSelector(key) + '"]');
          if (freshRow) {
            var freshOut = freshRow.querySelector('[data-dim-val]');
            value = freshOut ? (freshOut.textContent || '').trim() : '';
            resolved = true;
          }
        }

        if (!resolved && map) {
          var mapped = lookup(map, key, variantId);
          if (mapped !== undefined) {
            value = mapped === null ? '' : String(mapped);
            resolved = true;
          }
        }

        /* No data for this row anywhere: leave exactly what Liquid printed. */
        if (!resolved) return;

        if (value) {
          if (out.textContent !== value) {
            out.textContent = value;
            flash(row);
          }
          row.hidden = false;
          row.classList.remove('is-empty');
        } else {
          if (out.textContent !== '') flash(row);
          out.textContent = '';
          row.hidden = true;
          row.classList.add('is-empty');
        }
      });

      /* Keep the map current if Dawn handed us a newer server render. */
      if (freshRoot) {
        var freshMap = parseJsonScript(freshRoot.querySelector('[data-dews-spec-json]'));
        if (freshMap) this.__map = freshMap;
      }

      this.dataset.variantId = String(variantId);

      this.dispatchEvent(
        new CustomEvent('dews:spec-updated', {
          bubbles: true,
          detail: { variantId: String(variantId), source: freshRoot ? 'server' : 'json' },
        })
      );
    }
  }

  if (window.customElements) {
    window.customElements.define('dews-variant-info', DewsVariantInfo);
  }
})();
