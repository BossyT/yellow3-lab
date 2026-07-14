'use strict';
// Shared helpers for yellow3 Model Intelligence access (magic-link, Stripe-verified).
// Zero-dependency: Node built-ins + global fetch (Node 18+ on Vercel).
// Secrets are read from process.env only. Never hardcode keys here.
const crypto = require('crypto');

// Stripe product -> tier. Keep in sync with the catalogue.
const PRODUCTS = {
  'prod_Usp3qVABNp8n0g': 'professional',
  'prod_UspZO2dhBkJTMc': 'team',
};

// Public mailbox providers: a Team buyer on one of these does NOT open
// domain-wide access (else anyone @gmail.com would get in). Exact email only.
const PUBLIC_DOMAINS = new Set([
  'gmail.com', 'googlemail.com', 'outlook.com', 'hotmail.com', 'live.com',
  'yahoo.com', 'yahoo.co.uk', 'icloud.com', 'me.com', 'mac.com', 'aol.com',
  'proton.me', 'protonmail.com', 'gmx.com', 'gmx.net', 'msn.com', 'yandex.com',
  'zoho.com', 'fastmail.com', 'hey.com',
]);

function b64url(buf) {
  return Buffer.from(buf).toString('base64').replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}
function fromB64url(s) {
  s = s.replace(/-/g, '+').replace(/_/g, '/');
  return Buffer.from(s, 'base64').toString('utf8');
}

// Signed, self-describing token: base64url(JSON payload).base64url(HMAC-SHA256).
function sign(payload, secret) {
  const body = b64url(JSON.stringify(payload));
  const mac = b64url(crypto.createHmac('sha256', secret).update(body).digest());
  return body + '.' + mac;
}
function verify(token, secret) {
  if (!token || typeof token !== 'string' || token.indexOf('.') < 0) return null;
  const [body, mac] = token.split('.');
  if (!body || !mac) return null;
  const expect = b64url(crypto.createHmac('sha256', secret).update(body).digest());
  const a = Buffer.from(mac), b = Buffer.from(expect);
  if (a.length !== b.length || !crypto.timingSafeEqual(a, b)) return null;
  let obj;
  try { obj = JSON.parse(fromB64url(body)); } catch (e) { return null; }
  if (!obj || !obj.x || Date.now() > obj.x) return null;
  return obj;
}

function domainOf(email) {
  const m = String(email || '').toLowerCase().match(/@([^@]+)$/);
  return m ? m[1] : '';
}
function isEmail(email) {
  return /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(String(email || ''));
}

async function stripeGet(path, key) {
  const res = await fetch('https://api.stripe.com/v1/' + path, {
    headers: { Authorization: 'Bearer ' + key },
  });
  if (!res.ok) throw new Error('stripe ' + res.status + ' ' + (await res.text()));
  return res.json();
}

// Return the highest tier the email is entitled to, or null.
// 1) exact customer email with an active/trialing/past_due sub, then
// 2) Team domain match (company domain of an active Team subscriber).
async function tierForEmail(email, key) {
  email = String(email).toLowerCase().trim();
  const LIVE = ['active', 'trialing', 'past_due'];

  const custs = await stripeGet('customers?email=' + encodeURIComponent(email) + '&limit=10', key);
  let best = null;
  for (const c of (custs.data || [])) {
    const subs = await stripeGet('subscriptions?customer=' + c.id + '&status=all&limit=20', key);
    for (const s of (subs.data || [])) {
      if (!LIVE.includes(s.status)) continue;
      for (const it of (s.items && s.items.data) || []) {
        const t = PRODUCTS[it.price && it.price.product];
        if (t === 'team') return 'team';
        if (t) best = 'professional';
      }
    }
  }
  if (best) return best;

  const dom = domainOf(email);
  if (dom && !PUBLIC_DOMAINS.has(dom)) {
    let after = '';
    for (let page = 0; page < 10; page++) {
      const q = 'subscriptions?status=active&limit=100&expand[]=data.customer' + (after ? '&starting_after=' + after : '');
      const subs = await stripeGet(q, key);
      for (const s of (subs.data || [])) {
        const isTeam = ((s.items && s.items.data) || []).some(it => PRODUCTS[it.price && it.price.product] === 'team');
        if (!isTeam) continue;
        const cEmail = s.customer && s.customer.email;
        if (cEmail && domainOf(cEmail) === dom) return 'team';
      }
      if (!subs.has_more || !subs.data.length) break;
      after = subs.data[subs.data.length - 1].id;
    }
  }
  return null;
}

async function sendMagic(email, link, apiKey, from) {
  const html = [
    '<div style="font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;max-width:480px;margin:0 auto;color:#0e0e0e">',
    '<div style="height:4px;width:40px;background:#ffe000;margin-bottom:24px"></div>',
    '<h1 style="font-size:20px;font-weight:800;letter-spacing:-0.02em;margin:0 0 12px">Sign in to yellow3 Model Intelligence</h1>',
    '<p style="font-size:15px;color:#4b4b4b;line-height:1.5;margin:0 0 24px">Click the button below to access your reports. This link works once and expires in 15 minutes.</p>',
    '<a href="' + link + '" style="display:inline-block;background:#0e0e0e;color:#fff;font-size:13px;font-weight:700;letter-spacing:0.06em;text-transform:uppercase;text-decoration:none;padding:15px 30px">Open my access &#8594;</a>',
    '<p style="font-size:12px;color:#8a8a8a;line-height:1.5;margin:28px 0 0">If you did not request this, you can ignore this email. Your subscription is unaffected.</p>',
    '</div>',
  ].join('');
  const res = await fetch('https://api.resend.com/emails', {
    method: 'POST',
    headers: { Authorization: 'Bearer ' + apiKey, 'Content-Type': 'application/json' },
    body: JSON.stringify({ from, to: [email], subject: 'Your yellow3 Model Intelligence sign-in link', html }),
  });
  if (!res.ok) throw new Error('resend ' + res.status + ' ' + (await res.text()));
  return true;
}

function cookie(name, val, maxAgeSec) {
  return name + '=' + val + '; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=' + maxAgeSec;
}
function parseCookies(str) {
  const o = {};
  String(str || '').split(';').forEach(p => {
    const i = p.indexOf('=');
    if (i > 0) o[p.slice(0, i).trim()] = decodeURIComponent(p.slice(i + 1).trim());
  });
  return o;
}

module.exports = { PRODUCTS, sign, verify, tierForEmail, sendMagic, cookie, parseCookies, domainOf, isEmail };
