/* yellow3 cookie consent.
 *
 * THE SAME FILE RUNS ON BOTH PROPERTIES. yellow3.io serves it from the root and
 * buyer.yellow3.io serves a copy from its own public/. It has no dependencies
 * and no build step, because one of the two sites has neither.
 *
 * WHAT THIS ACTUALLY GATES, TODAY: nothing. Verified before it was written -
 * yellow3.io, buyer.yellow3.io and /eu-desk each set zero cookies, zero
 * localStorage and zero sessionStorage on arrival. That is not an accident;
 * Google Analytics was removed from yellow3.io on 14 August precisely because
 * it loaded before anyone was asked.
 *
 * So this is the gate that has to exist BEFORE anything comes back, and it is
 * built to be the real thing rather than a notice:
 *
 *   NOTHING NON-ESSENTIAL LOADS UNTIL A CHOICE IS MADE. Not on dismiss, not on
 *   scroll, not on "continued use". Prior consent means prior.
 *
 *   REJECT IS AS EASY AS ACCEPT. Same size, same weight, same position, one
 *   click each. A reject buried behind a settings panel is the pattern the
 *   Danish Datatilsynet has repeatedly said does not count.
 *
 *   NO PRE-TICKED ANYTHING. The stored default is refusal.
 *
 *   THE CHOICE IS WITHDRAWABLE. A standing control reopens it, because consent
 *   that cannot be taken back was never consent.
 *
 * THE CONSENT RECORD ITSELF IS EXEMPT. It is one localStorage key remembering
 * what the visitor chose; storage strictly necessary to provide what the user
 * asked for does not need consent, and asking permission to remember a refusal
 * would be absurd.
 *
 * HOW A SCRIPT USES IT:
 *
 *     if (window.y3Consent.granted('analytics')) { ...load it... }
 *     window.addEventListener('y3-consent-change', function (e) {
 *       if (e.detail.analytics) { ...load it now... }
 *     });
 *
 * ANALYTICS LOADS AT THE BOTTOM OF THIS FILE, behind that call and nowhere
 * else - GA4 on the public site, and only there. The buyer app loads its own
 * tag through app/analytics.tsx against the same consent record, which is why
 * the loader here checks the hostname before doing anything.
 */
(function () {
  'use strict';

  var KEY = 'y3-consent';
  var VERSION = 1;

  // Shown to every visitor, not only to EU ones.
  //
  // Geo-detection would need either a server (yellow3.io is static) or a
  // third-party lookup (which is itself a request to somebody about a visitor,
  // before consent). And it fails in the direction that matters: an EU resident
  // on a VPN, or travelling, would be missed. Showing it to a visitor outside
  // the EU costs one dismissal.
  var ASK_EVERYONE = true;

  function read() {
    try {
      var raw = window.localStorage.getItem(KEY);
      if (!raw) return null;
      var v = JSON.parse(raw);
      return (v && v.v === VERSION) ? v : null;   // an old shape is no consent
    } catch (e) {
      return null;                                 // storage blocked: ask again
    }
  }

  // REFUSING HAS TO REMOVE WHAT WAS ALREADY THERE.
  //
  // Analytics ran on yellow3.io before 14 August with no gate, and its cookies
  // have a two-year lifetime - so a device that visited then still carries
  // `_ga` and `_ga_K3JXMM2VG5` on `.yellow3.io` today. Found on a real device,
  // not assumed. Consent that only governs the future leaves those in place and
  // lets a visitor who has just said no keep being identified by them.
  //
  // Both hosts can write to `.yellow3.io`, so clearing from either clears for
  // both. Every plausible domain and path is expired, because a cookie set on a
  // different combination than the one guessed is a cookie that survives.
  function clearAnalyticsCookies() {
    var names = [];
    var jar = String(document.cookie || '').split(';');
    for (var i = 0; i < jar.length; i++) {
      var n = jar[i].split('=')[0].trim();
      if (n === '_ga' || n.indexOf('_ga_') === 0 || n === '_gid' || n.indexOf('_gac_') === 0) {
        names.push(n);
      }
    }
    if (!names.length) return;

    var host = window.location.hostname;
    var domains = ['', host, '.' + host];
    var parts = host.split('.');
    for (var d = 0; d < parts.length - 1; d++) {
      domains.push('.' + parts.slice(d).join('.'));   // .buyer.yellow3.io, .yellow3.io, .io
    }
    var past = 'Thu, 01 Jan 1970 00:00:00 GMT';
    for (var j = 0; j < names.length; j++) {
      for (var k = 0; k < domains.length; k++) {
        document.cookie = names[j] + '=; expires=' + past + '; path=/'
          + (domains[k] ? '; domain=' + domains[k] : '');
      }
    }
  }

  function write(analytics) {
    var record = { v: VERSION, analytics: !!analytics, at: new Date().toISOString() };
    try { window.localStorage.setItem(KEY, JSON.stringify(record)); } catch (e) { /* private mode */ }
    if (!analytics) clearAnalyticsCookies();
    window.dispatchEvent(new CustomEvent('y3-consent-change', { detail: record }));
    return record;
  }

  var current = read();

  window.y3Consent = {
    granted: function (purpose) {
      var c = read();
      return !!(c && c[purpose === 'analytics' ? 'analytics' : purpose]);
    },
    record: read,
    reopen: function () { show(); },
  };

  // ------------------------------------------------------------- analytics
  //
  // GA4 for the PUBLIC SITE ONLY, loaded here because this file is already on
  // every public page and already knows the answer.
  //
  // WHY NOT A SWEEP. Adding a tag to 641 pages is exactly the transform that
  // removed 657 lines from the CMS on 14 August. This script is already on
  // 641 of the 643 html files; the two without it are admin.html - the CMS,
  // which holds a GitHub token and must never be measured - and the Search
  // Console verification token. Putting the loader here inherits that
  // coverage, and admin.html stays excluded because it was never included.
  //
  // WHY THE HOSTNAME CHECK. This file is byte-identical on yellow3.io and on
  // buyer.yellow3.io - check-consent.js fails the build if they drift. The
  // buyer app loads its own tag through app/analytics.tsx, behind the same
  // consent record and off its private routes. Without this check, a buyer
  // page would load GA twice and every page_view would be counted twice.
  //
  // SAME MEASUREMENT ID AS BUYER, deliberately. yellow3.io -> buyer.yellow3.io
  // is one journey, and two properties would make it two strangers.
  var GA_ID = 'G-K3JXMM2VG5';
  var loaded = false;

  function isPublicSite() {
    var h = location.hostname;
    return h === 'yellow3.io' || h === 'www.yellow3.io';
  }

  function loadAnalytics() {
    if (loaded || !isPublicSite()) return;
    if (!window.y3Consent.granted('analytics')) return;
    loaded = true;

    window.dataLayer = window.dataLayer || [];
    // Must be a real function declaration using `arguments` - gtag pushes the
    // arguments object itself, and an arrow or a rest parameter changes the
    // shape of what lands in dataLayer.
    window.gtag = function () { window.dataLayer.push(arguments); };
    window.gtag('js', new Date());
    window.gtag('config', GA_ID);

    var t = document.createElement('script');
    t.async = true;
    t.src = 'https://www.googletagmanager.com/gtag/js?id=' + GA_ID;
    document.head.appendChild(t);
  }

  loadAnalytics();
  // Accepting mounts the tag immediately rather than on the next navigation.
  window.addEventListener('y3-consent-change', function (e) {
    if (e && e.detail && e.detail.analytics) loadAnalytics();
  });

  // THE STYLES TRAVEL WITH THE SCRIPT, rather than living in a stylesheet.
  //
  // This runs on 640 static pages and on a Next app, and those do not share a
  // stylesheet. More to the point, the public site's CSS is design-frozen and
  // its packages are integrated class for class - appending to it to make a
  // consent box work would be exactly the kind of edit that gate exists to
  // refuse. One <style>, injected once, owned by this file.
  //
  // Arial, because that is the one public typeface. Yellow only as the accent
  // on the affirmative choice, never as a nudge: both buttons are the same
  // size, weight and shape.
  function styles() {
    if (document.getElementById('y3-consent-css')) return;
    var css = document.createElement('style');
    css.id = 'y3-consent-css';
    css.textContent = [
      '.y3-consent{position:fixed;left:0;right:0;bottom:0;z-index:2147483000;',
      'background:#fff;border-top:1px solid #e0e0da;',
      'box-shadow:0 -6px 24px rgba(0,0,0,.08);',
      'font-family:Arial,Helvetica,sans-serif;color:#111}',
      '.y3-consent-inner{max-width:1100px;margin:0 auto;padding:20px 24px;',
      'display:flex;gap:26px;align-items:center;justify-content:space-between;',
      'flex-wrap:wrap}',
      '.y3-consent-copy{flex:1 1 420px;min-width:0}',
      '.y3-consent-copy strong{display:block;font-size:15px;margin-bottom:5px}',
      '.y3-consent-copy p{margin:0;font-size:13px;line-height:1.55;color:#4f4f4b}',
      '.y3-consent-copy a{color:#111}',
      '.y3-consent-actions{display:flex;gap:10px;flex:0 0 auto}',
      '.y3-consent-btn{font-family:inherit;font-size:13px;font-weight:700;',
      'height:42px;padding:0 18px;border-radius:8px;border:1px solid #111;',
      'background:#fff;color:#111;cursor:pointer;white-space:nowrap}',
      '.y3-consent-btn+.y3-consent-btn{background:#ffd600;border-color:#ffd600}',
      '@media(max-width:640px){.y3-consent-inner{padding:16px}',
      '.y3-consent-actions{width:100%}.y3-consent-btn{flex:1}}',
    ].join('');
    document.head.appendChild(css);
  }

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text) n.textContent = text;
    return n;
  }

  function show() {
    if (document.getElementById('y3-consent')) return;
    styles();

    var wrap = el('div', 'y3-consent');
    wrap.id = 'y3-consent';
    wrap.setAttribute('role', 'dialog');
    wrap.setAttribute('aria-live', 'polite');
    wrap.setAttribute('aria-label', 'Cookies');

    var inner = el('div', 'y3-consent-inner');

    var copy = el('div', 'y3-consent-copy');
    copy.appendChild(el('strong', null, 'Cookies on this site'));
    var p = el('p', null,
      'We use no analytics or advertising cookies unless you say yes. '
      + 'Choosing no changes nothing about what the site does. ');
    var link = el('a', null, 'How we use cookies');
    link.href = '/cookies';
    p.appendChild(link);
    copy.appendChild(p);

    var actions = el('div', 'y3-consent-actions');

    // Reject first, and identical in weight. The order is deliberate.
    var no = el('button', 'y3-consent-btn', 'No, only essentials');
    no.type = 'button';
    no.addEventListener('click', function () { write(false); close(); });

    var yes = el('button', 'y3-consent-btn', 'Yes, allow analytics');
    yes.type = 'button';
    yes.addEventListener('click', function () { write(true); close(); });

    actions.appendChild(no);
    actions.appendChild(yes);
    inner.appendChild(copy);
    inner.appendChild(actions);
    wrap.appendChild(inner);
    document.body.appendChild(wrap);

    // Focus the dialog so a keyboard user is not left hunting for it. Not a
    // focus TRAP: this is not modal, and trapping a visitor in a cookie box to
    // force a decision is the coercion the rules exist to stop.
    no.focus();
  }

  function close() {
    var n = document.getElementById('y3-consent');
    if (n && n.parentNode) n.parentNode.removeChild(n);
  }

  function ready(fn) {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', fn);
    } else { fn(); }
  }

  ready(function () {
    // A standing refusal keeps clearing them. Somebody who declined last month
    // and picked up an old cookie since should not have to decline again.
    if (current && !current.analytics) clearAnalyticsCookies();

    if (!current && ASK_EVERYONE) show();

    // A standing way back in, wherever a page offers one.
    var links = document.querySelectorAll('[data-y3-consent-reopen]');
    for (var i = 0; i < links.length; i++) {
      links[i].addEventListener('click', function (e) {
        e.preventDefault();
        show();
      });
    }
  });
})();
