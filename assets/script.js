/* ==========================================================================
   Dew's Furniture — homepage interactions
   Vanilla JS, no dependencies. Every module bails out safely if its markup
   isn't on the page, so sections can be reordered or removed freely.
   ========================================================================== */
(function () {
  'use strict';

  var $  = function (sel, ctx) { return (ctx || document).querySelector(sel); };
  var $$ = function (sel, ctx) { return Array.prototype.slice.call((ctx || document).querySelectorAll(sel)); };

  var reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ------------------------------------------------------------------
     Header — solid/bordered once the page has scrolled
     ------------------------------------------------------------------ */
  (function header() {
    var el = $('#header') || $('.dews-header');
    if (!el) return;

    var onScroll = function () {
      el.classList.toggle('is-stuck', window.scrollY > 8);
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
  })();

  /* ------------------------------------------------------------------
     Search panel
     ------------------------------------------------------------------ */
  (function search() {
    var panel = $('#search');
    var open  = $('#searchBtn');
    var close = $('#searchClose');
    var input = $('#searchInput');
    if (!panel || !open) return;

    var setOpen = function (state) {
      panel.classList.toggle('is-open', state);
      open.setAttribute('aria-expanded', String(state));
      if (state && input) input.focus();
    };

    open.addEventListener('click', function () {
      setOpen(!panel.classList.contains('is-open'));
    });
    if (close) close.addEventListener('click', function () { setOpen(false); open.focus(); });

    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && panel.classList.contains('is-open')) {
        setOpen(false);
        open.focus();
      }
    });
  })();

  /* ------------------------------------------------------------------
     Mobile drawer
     ------------------------------------------------------------------ */
  (function drawer() {
    var el    = $('#drawer');
    var scrim = $('#scrim');
    var open  = $('#menuBtn');
    var close = $('#drawerClose');
    if (!el || !open) return;

    var setOpen = function (state) {
      el.classList.toggle('is-open', state);
      if (scrim) {
        scrim.classList.toggle('is-open', state);
        scrim.hidden = !state;
      }
      open.setAttribute('aria-expanded', String(state));
      document.body.style.overflow = state ? 'hidden' : '';
      if (state && close) close.focus();
    };

    open.addEventListener('click', function () { setOpen(true); });
    if (close) close.addEventListener('click', function () { setOpen(false); open.focus(); });
    if (scrim) scrim.addEventListener('click', function () { setOpen(false); });

    $$('a', el).forEach(function (a) {
      a.addEventListener('click', function () { setOpen(false); });
    });

    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && el.classList.contains('is-open')) {
        setOpen(false);
        open.focus();
      }
    });

    $$('.drawer__toggle', el).forEach(function (btn) {
      var sub = document.getElementById(btn.getAttribute('aria-controls'));
      if (!sub) return;

      btn.addEventListener('click', function () {
        var isOpen = btn.classList.toggle('is-open');
        btn.setAttribute('aria-expanded', String(isOpen));
        sub.style.maxHeight = isOpen ? sub.scrollHeight + 'px' : '0px';
      });
    });
  })();

  /* ------------------------------------------------------------------
     Room index — hovering/focusing a room swaps the large stage image
     ------------------------------------------------------------------ */
  (function rooms() {
    var list  = $('#roomsList');
    var stage = $('#roomsStage');
    if (!list || !stage) return;

    var items  = $$('.rooms__item', list);
    var frames = $$('img', stage);

    var activate = function (index) {
      items.forEach(function (item, i) { item.classList.toggle('is-active', i === index); });
      frames.forEach(function (img, i) { img.classList.toggle('is-active', i === index); });
    };

    items.forEach(function (item, i) {
      item.addEventListener('mouseenter', function () { activate(i); });
      item.addEventListener('focusin', function () { activate(i); });
    });
  })();

/* ------------------------------------------------------------------
     Hero hotspots — allow navigation if it's a link
     ------------------------------------------------------------------ */
  (function hotspots() {
    var spots = $$('.hotspot');
    if (!spots.length) return;

    spots.forEach(function (spot) {
      spot.addEventListener('click', function (e) {
        if (window.innerWidth <= 1024 && !spot.classList.contains('is-open')) {
          e.preventDefault();
          var wasOpen = spot.classList.contains('is-open');
          spots.forEach(function (s) { s.classList.remove('is-open'); });
          spot.classList.toggle('is-open', !wasOpen);
        }
      });
    });

    document.addEventListener('click', function (e) {
      if (!e.target.closest('.hotspot')) {
        spots.forEach(function (s) { s.classList.remove('is-open'); });
      }
    });
  })();

  /* ------------------------------------------------------------------
     Product rail — arrows + scroll progress bar
     ------------------------------------------------------------------ */
  (function rails() {
    $$('[data-rail]').forEach(function (rail) {
      var track = $('[data-rail-track]', rail);
      var bar   = $('[data-rail-bar]', rail);
      var prev  = $('[data-rail-prev]', rail);
      var next  = $('[data-rail-next]', rail);
      if (!track) return;

      var page = function () {
        return Math.max(track.clientWidth * 0.8, 240);
      };

      var update = function () {
        var max = track.scrollWidth - track.clientWidth;

        if (bar) {
          var visible = track.clientWidth / track.scrollWidth;
          var ratio   = max > 0 ? track.scrollLeft / max : 0;
          bar.style.width = Math.max(visible * 100, 12) + '%';
          bar.style.transform = 'translateX(' + (ratio * ((1 / Math.max(visible, 0.12)) - 1) * 100) + '%)';
        }
        if (prev) prev.disabled = track.scrollLeft <= 2;
        if (next) next.disabled = track.scrollLeft >= max - 2;
      };

      if (prev) prev.addEventListener('click', function () { track.scrollBy({ left: -page(), behavior: reduceMotion ? 'auto' : 'smooth' }); });
      if (next) next.addEventListener('click', function () { track.scrollBy({ left:  page(), behavior: reduceMotion ? 'auto' : 'smooth' }); });

      track.addEventListener('scroll', update, { passive: true });
      window.addEventListener('resize', update);
      update();
    });
  })();

  /* ------------------------------------------------------------------
     Wishlist toggle
     ------------------------------------------------------------------ */
  (function wishlist() {
    $$('[data-wishlist]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var saved = btn.classList.toggle('is-saved');
        btn.setAttribute('aria-pressed', String(saved));
      });
    });
  })();

/* ------------------------------------------------------------------
     AJAX Quick Add (Dawn Native renderContents & Class Sync Fix)
     ------------------------------------------------------------------ */
  (function quickAdd() {
    $$('form[action="/cart/add"]').forEach(function (form) {
      
      if (form.getAttribute('data-type') === 'add-to-cart-form' || form.closest('product-form')) {
        return; 
      }

      form.addEventListener('submit', function (e) {
        e.preventDefault();
        e.stopImmediatePropagation(); 

        var btn = form.querySelector('button[type="submit"]');
        if (!btn || btn.disabled) return;

        var textTarget = btn.querySelector('span') || btn;
        var originalText = textTarget.textContent;
        
        textTarget.textContent = 'Adding...';
        btn.disabled = true;

        var formData = new FormData(form);
        
        // Shopify standard section parameters
        formData.append('sections', 'cart-drawer,cart-icon-bubble');
        formData.append('sections_url', window.location.pathname);

        fetch('/cart/add.js', {
          method: 'POST',
          body: formData
        })
        .then(function (res) {
          if (!res.ok) throw new Error('Network response was not ok');
          return res.json();
        })
        .then(function (parsedState) {
          textTarget.textContent = 'Added! ✓';

          // DAWN NATIVE METHOD WITH BULLETPROOF FIX: Remove 'is-empty' class instantly so items don't hide
          var cartDrawerElement = document.querySelector('cart-drawer');
          if (cartDrawerElement && typeof cartDrawerElement.renderContents === 'function') {
             cartDrawerElement.renderContents(parsedState);
             
             setTimeout(function() {
               cartDrawerElement.classList.remove('is-empty');
               if (typeof cartDrawerElement.open === 'function') {
                 cartDrawerElement.open();
               } else {
                 document.documentElement.classList.add('cart-drawer-open');
               }
             }, 50);

          } else {
             window.location.reload();
          }

          setTimeout(function () {
            textTarget.textContent = originalText;
            btn.disabled = false;
          }, 2000);
        })
        .catch(function (err) {
          console.error('Quick add error:', err);
          textTarget.textContent = 'Error';
          setTimeout(function () {
            textTarget.textContent = originalText;
            btn.disabled = false;
          }, 2000);
        });
      });
    });
  })();

/* ------------------------------------------------------------------
     Quick view modal
     ------------------------------------------------------------------ */
  (function quickview() {
    if (!document.getElementById('quickview')) {
      var modalMarkup = `
        <div class="modal" id="quickview" hidden>
          <div class="modal__panel">
            <button class="modal__close" id="qvClose" aria-label="Close modal"><svg aria-hidden="true"><use href="#i-close"/></svg></button>
            <div class="modal__media"><img id="qvImg" src="" alt=""></div>
            <div class="modal__body">
              <h3 id="qvName"></h3>
              <p class="price-row"><span class="price" id="qvPrice"></span> <span class="price--was" id="qvWas"></span></p>
              <p class="desc" id="qvDesc"></p>
              <div class="modal__actions">
                <a href="#" id="qvLink" class="btn btn--block">View full details <svg aria-hidden="true"><use href="#i-arrow"/></svg></a>
              </div>
            </div>
          </div>
        </div>
      `;
      document.body.insertAdjacentHTML('beforeend', modalMarkup);
    }

    var modal = $('#quickview');
    if (!modal) return;

    var img   = $('#qvImg');
    var name  = $('#qvName');
    var price = $('#qvPrice');
    var was   = $('#qvWas');
    var desc  = $('#qvDesc');
    var close = $('#qvClose');
    var lastFocus = null;

    var setOpen = function (state) {
      modal.classList.toggle('is-open', state);
      modal.hidden = !state;
      document.body.style.overflow = state ? 'hidden' : '';
      if (state) {
        if (close) close.focus();
      } else if (lastFocus) {
        lastFocus.focus();
      }
    };

    $$('[data-quickview]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        lastFocus = btn;
        var wasPrice = btn.dataset.was || '';

        if (img)   { img.src = btn.dataset.img || ''; img.alt = btn.dataset.name || ''; }
        if (name)  name.textContent  = btn.dataset.name || '';
        if (price) price.textContent = btn.dataset.price || '';
        if (was)   { was.textContent = wasPrice; was.style.display = wasPrice ? '' : 'none'; }
        if (desc)  desc.textContent  = btn.dataset.desc || '';

        var productCard = btn.closest('.product');
        if (productCard) {
          var pLink = productCard.querySelector('h3 a');
          var qvLink = $('#qvLink');
          if (pLink && qvLink) qvLink.href = pLink.href;
        }

        setOpen(true);
      });
    });

    if (close) close.addEventListener('click', function () { setOpen(false); });
    modal.addEventListener('click', function (e) { if (e.target === modal) setOpen(false); });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && modal.classList.contains('is-open')) setOpen(false);
    });
  })();

  /* ------------------------------------------------------------------
     FAQ accordion
     ------------------------------------------------------------------ */
  (function faq() {
    var items = $$('.faq__item');
    if (!items.length) return;

    var setOpen = function (item, state) {
      var panel = $('.faq__a', item);
      var btn   = $('.faq__q', item);
      item.classList.toggle('is-open', state);
      if (btn)   btn.setAttribute('aria-expanded', String(state));
      if (panel) panel.style.maxHeight = state ? panel.scrollHeight + 'px' : '0px';
    };

    items.forEach(function (item) {
      var btn = $('.faq__q', item);
      if (!btn) return;

      if (item.classList.contains('is-open')) setOpen(item, true);

      btn.addEventListener('click', function () {
        var willOpen = !item.classList.contains('is-open');
        items.forEach(function (other) { setOpen(other, false); });
        setOpen(item, willOpen);
      });
    });

    var resync = function () {
      items.forEach(function (item) {
        if (item.classList.contains('is-open')) setOpen(item, true);
      });
    };

    window.addEventListener('resize', resync);
    window.addEventListener('load', resync);
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(resync);
  })();

  /* ------------------------------------------------------------------
     Reveal on scroll
     ------------------------------------------------------------------ */
  (function reveal() {
    var els = $$('.reveal, .reveal-img');
    if (!els.length) return;

    if (reduceMotion || !('IntersectionObserver' in window)) {
      els.forEach(function (el) { el.classList.add('is-in'); });
      return;
    }

    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        entry.target.classList.add('is-in');
        io.unobserve(entry.target);
      });
    }, { threshold: 0.12, rootMargin: '0px 0px -8% 0px' });

    els.forEach(function (el) { io.observe(el); });

    var sweep = function () {
      var vh = window.innerHeight || document.documentElement.clientHeight;
      els.forEach(function (el) {
        if (el.classList.contains('is-in')) return;
        var r = el.getBoundingClientRect();
        if (r.top < vh * 0.92 && r.bottom > 0) el.classList.add('is-in');
      });
    };

    window.addEventListener('scroll', sweep, { passive: true });
    window.addEventListener('resize', sweep);
    window.addEventListener('load', sweep);
    sweep();
  })();

  /* ------------------------------------------------------------------
     Promo countdown
     ------------------------------------------------------------------ */
  (function countdown() {
    var root = $('#countdown');
    if (!root) return;

    var d = $('#cd-d'), h = $('#cd-h'), m = $('#cd-m'), s = $('#cd-s');
    if (!d || !h || !m || !s) return;

    var hours = parseInt(root.dataset.hours, 10) || 72;
    var key   = 'dews-offer-end';
    var end   = parseInt(window.localStorage.getItem(key), 10);

    if (!end || isNaN(end) || end < Date.now()) {
      end = Date.now() + hours * 3600 * 1000;
      try { window.localStorage.setItem(key, String(end)); } catch (e) { }
    }

    var pad = function (n) { return n < 10 ? '0' + n : String(n); };

    var tick = function () {
      var left = Math.max(0, end - Date.now());
      var secs = Math.floor(left / 1000);

      d.textContent = pad(Math.floor(secs / 86400));
      h.textContent = pad(Math.floor(secs / 3600) % 24);
      m.textContent = pad(Math.floor(secs / 60) % 60);
      s.textContent = pad(secs % 60);
    };

    tick();
    setInterval(tick, 1000);
  })();

  /* ------------------------------------------------------------------
     Newsletter
     ------------------------------------------------------------------ */
  (function newsletter() {
    var form = $('#newsForm');
    var msg  = $('#formMsg');
    if (!form) return;

    form.addEventListener('submit', function (e) {
      e.preventDefault();
      var input = $('#newsEmail');
      var value = input ? input.value.trim() : '';
      var valid = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(value);

      if (!msg) return;
      msg.textContent = valid
        ? 'Thanks — check your inbox to confirm your subscription.'
        : 'Please enter a valid email address.';
      msg.className = 'form-msg ' + (valid ? 'is-ok' : 'is-err');

      if (valid) form.reset();
      else if (input) input.focus();
    });
  })();

  /* ------------------------------------------------------------------
     Mobile sticky CTA
     ------------------------------------------------------------------ */
  (function mobileCta() {
    var bar = $('#mobileCta');
    if (!bar) return;

    var onScroll = function () {
      var show = window.scrollY > window.innerHeight * 0.6;
      bar.classList.toggle('is-visible', show);
      document.body.classList.toggle('has-mobile-cta', show);
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
  })();

  /* ------------------------------------------------------------------
     Product Card Swatch Click (Image Swap & Active State)
     ------------------------------------------------------------------ */
  (function swatchClick() {
    var swatches = document.querySelectorAll('[data-swatch-hover]');
    if (!swatches.length) return;

    swatches.forEach(function(swatch) {
      swatch.addEventListener('click', function(e) {
        e.preventDefault();
        
        var productCard = swatch.closest('.product');
        if (!productCard) return;

        var allCardSwatches = productCard.querySelectorAll('[data-swatch-hover]');
        allCardSwatches.forEach(function(s) { s.classList.remove('is-active'); });
        swatch.classList.add('is-active');

        var newImgUrl = swatch.getAttribute('data-variant-img');
        if (!newImgUrl) return; 

        var mainImg = productCard.querySelector('[data-main-img]');
        var hoverImg = productCard.querySelector('.img-hover');

        if (mainImg) {
          mainImg.src = newImgUrl;
          mainImg.removeAttribute('srcset'); 
        }
        
        if (hoverImg) {
          hoverImg.src = newImgUrl;
          hoverImg.removeAttribute('srcset');
        }
      });
    });
  })();

  document.addEventListener('DOMContentLoaded', function() {
    const cartIcon = document.getElementById('cart-icon-bubble');
    if (cartIcon) {
      cartIcon.addEventListener('click', function(e) {
        const drawer = document.querySelector('cart-drawer');
        if (drawer) {
          e.preventDefault();
          if (typeof drawer.open === 'function') {
            drawer.open();
          } else {
            document.documentElement.classList.add('cart-drawer-open');
          }
        }
      });
    }
  });
  
})();