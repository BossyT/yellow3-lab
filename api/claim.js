'use strict';
// Claim a DPP Supplier Register profile.
//
// The whole check is: does the sender's email domain match the domain that
// defines this row? The register's join key IS the domain, so a work email at
// that domain proves the person belongs to the company. No accounts, no
// moderation queue, no inbox full of "please update our entry".
//
// Zero-dependency: Node built-ins + global fetch, same as the rest of /api.

const fs = require('fs');
const path = require('path');
const { domainOf, isEmail } = require('./_lib/util');

const PUBLIC_MAILBOXES = new Set([
  'gmail.com', 'googlemail.com', 'outlook.com', 'hotmail.com', 'live.com',
  'yahoo.com', 'yahoo.co.uk', 'icloud.com', 'me.com', 'mac.com', 'aol.com',
  'proton.me', 'protonmail.com', 'gmx.com', 'gmx.net', 'msn.com', 'yandex.com',
  'zoho.com', 'fastmail.com', 'hey.com',
]);

let REGISTER = null;
function register() {
  if (!REGISTER) {
    const p = path.join(process.cwd(), 'research', 'dpp-suppliers.json');
    REGISTER = JSON.parse(fs.readFileSync(p, 'utf8')).suppliers || [];
  }
  return REGISTER;
}

// domain first, then alias_domains - a parent company or a product brand that
// has its own pointer row still reaches the right profile.
function findSupplier(id, dom) {
  const rows = register();
  const row = rows.find(r => r.id === id);
  if (!row) return null;
  const owned = [row.domain]
    .concat(String(row.alias_domains || '').split(',').map(s => s.trim()))
    .filter(Boolean)
    .map(s => s.toLowerCase());
  return owned.includes(dom) ? row : null;
}

async function send(apiKey, from, to, subject, html) {
  const res = await fetch('https://api.resend.com/emails', {
    method: 'POST',
    headers: { Authorization: 'Bearer ' + apiKey, 'Content-Type': 'application/json' },
    body: JSON.stringify({ from, to: [to], subject, html }),
  });
  if (!res.ok) throw new Error('resend ' + res.status + ' ' + (await res.text()));
}

const shell = inner =>
  '<div style="font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;max-width:520px;margin:0 auto;color:#0e0e0e">'
  + '<div style="height:4px;width:40px;background:#ffe000;margin-bottom:24px"></div>' + inner + '</div>';

module.exports = async (req, res) => {
  if (req.method !== 'POST') {
    res.setHeader('Allow', 'POST');
    return res.status(405).json({ ok: false });
  }

  let body = req.body;
  if (typeof body === 'string') { try { body = JSON.parse(body); } catch (e) { body = {}; } }
  const email = String((body && body.email) || '').toLowerCase().trim();
  const id = String((body && body.supplier) || '').trim();

  // Always answer the same way. Never reveal whether a domain matched, or the
  // form becomes a way to enumerate who works where.
  const ok = () => res.status(200).json({ ok: true });

  if (!isEmail(email) || !id) return ok();

  const dom = domainOf(email);
  if (!dom || PUBLIC_MAILBOXES.has(dom)) return ok();

  let row;
  try { row = findSupplier(id, dom); } catch (e) { return ok(); }
  if (!row) return ok();

  const KEY = process.env.RESEND_API_KEY;
  const FROM = process.env.FROM_EMAIL;
  const NOTIFY = process.env.CLAIM_NOTIFY_EMAIL || FROM;
  if (!KEY || !FROM) return ok();

  const url = 'https://yellow3.io/research/digital-product-passport/' + row.id;
  try {
    await send(KEY, FROM, email,
      'Your claim on the yellow3 DPP Supplier Register',
      shell(
        '<h1 style="font-size:20px;font-weight:800;letter-spacing:-0.02em;margin:0 0 12px">Claim received for ' + row.name + '</h1>'
        + '<p style="font-size:15px;color:#4b4b4b;line-height:1.55;margin:0 0 18px">We verified that you wrote from <b>' + dom + '</b>, the domain on record for this profile, so the claim is confirmed.</p>'
        + '<p style="font-size:15px;color:#4b4b4b;line-height:1.55;margin:0 0 18px">Reply to this email with anything you want on the company-supplied side of your profile: a logo, a one-line description, a contact link, and your answers to the ten capability checks. It appears in its own layer, marked as yours.</p>'
        + '<p style="font-size:15px;color:#4b4b4b;line-height:1.55;margin:0 0 24px">What we verified independently stays as it is. If something there is wrong, send the correction with a source and we will check it, fix it and log the change.</p>'
        + '<a href="' + url + '" style="display:inline-block;background:#0e0e0e;color:#fff;font-size:13px;font-weight:700;letter-spacing:0.06em;text-transform:uppercase;text-decoration:none;padding:15px 30px">View your profile &#8594;</a>'
        + '<p style="font-size:12px;color:#8a8a8a;line-height:1.5;margin:28px 0 0">If you did not request this, you can ignore it. Nothing on the profile has changed.</p>'));

    if (NOTIFY) {
      await send(KEY, FROM, NOTIFY,
        'Profile claimed: ' + row.name,
        shell(
          '<h1 style="font-size:18px;font-weight:800;margin:0 0 12px">' + row.name + '</h1>'
          + '<p style="font-size:14px;color:#4b4b4b;line-height:1.6;margin:0">'
          + '<b>Claimed by:</b> ' + email + '<br>'
          + '<b>Domain matched:</b> ' + dom + '<br>'
          + '<b>Row:</b> ' + row.id + '<br>'
          + '<b>Profile:</b> <a href="' + url + '">' + url + '</a></p>'));
    }
  } catch (e) {
    // Delivery failed; still answer identically rather than leaking anything.
  }
  return ok();
};
