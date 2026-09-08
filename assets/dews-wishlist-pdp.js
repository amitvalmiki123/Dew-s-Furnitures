/* ==========================================================================
   Dew's PDP — Add to cart + Wishlist side by side, Buy Now full-width below
   Moves Wishlist Hero's automatic product-page button
   (.wishlisthero-product-page-button-container) into Dawn's
   .product-form__buttons row, right after the Add to cart submit.
   - Bails out safely if the row or the app button isn't on the page.
   - Keeps watching (cheap childList observer) so theme-editor
     re-renders and late app injection are handled too.
   ========================================================================== */
(function () {
  'use strict';

  var ROW_SEL = '.dews-product .product-form__buttons';
  var BTN_SEL = '.wishlisthero-product-page-button-container';
  var DONE_CLASS = 'dews-wishlist-inline';

  function place() {
    var row = document.querySelector(ROW_SEL);
    if (!row) return;
    var btn = document.querySelector(BTN_SEL + ':not(.' + DONE_CLASS + ')');
    if (!btn) return;

    var pay = row.querySelector('.shopify-payment-button');
    if (pay) {
      row.insertBefore(btn, pay);
    } else {
      row.appendChild(btn);
    }
    btn.classList.add(DONE_CLASS);

    // Safety: a <button> inside the buy <form> must never submit it.
    btn.querySelectorAll('button:not([type])').forEach(function (b) {
      b.setAttribute('type', 'button');
    });
  }

  place();

  if ('MutationObserver' in window) {
    var obs = new MutationObserver(place);
    obs.observe(document.documentElement, { childList: true, subtree: true });
  } else {
    // Very old browsers: retry a few times instead.
    var tries = 0;
    var timer = setInterval(function () {
      tries += 1;
      place();
      if (tries >= 20) clearInterval(timer);
    }, 500);
  }

  // Re-run after theme-editor section reloads.
  document.addEventListener('shopify:section:load', place);
})();
