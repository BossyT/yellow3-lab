'use strict';
// Claim a DPP Supplier Register profile.
//
// The whole check is: does the sender's email domain match the domain that
// defines this row? The register's join key IS the domain, so a work email at
// that domain proves the person belongs to the company. No accounts, no
// moderation queue, no inbox full of "please update our entry".
//
// A match emails a signed link that opens the company's own editor. Nobody at
// yellow3 is in the loop: the supplier writes their own layer themselves.
//
// Zero-dependency: Node built-ins + global fetch, same as the rest of /api.

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { domainOf, isEmail, sign } = require('./_lib/util');
const claimlock = require('./_lib/claimlock');

const PUBLIC_MAILBOXES = new Set([
  'gmail.com', 'googlemail.com', 'outlook.com', 'hotmail.com', 'live.com',
  'yahoo.com', 'yahoo.co.uk', 'icloud.com', 'me.com', 'mac.com', 'aol.com',
  'proton.me', 'protonmail.com', 'gmx.com', 'gmx.net', 'msn.com', 'yandex.com',
  'zoho.com', 'fastmail.com', 'hey.com',
]);

const SITE = 'https://www.yellow3.io';
const LINK_TTL_MS = 24 * 60 * 60 * 1000;

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
function ownedDomains(row) {
  return [row.domain]
    .concat(String(row.alias_domains || '').split(',').map(s => s.trim()))
    .filter(Boolean)
    .map(s => s.toLowerCase());
}

async function send(apiKey, from, to, subject, html, replyTo) {
  const payload = { from, to: [to], subject, html };
  if (replyTo) payload.reply_to = [replyTo];
  const res = await fetch('https://api.resend.com/emails', {
    method: 'POST',
    headers: { Authorization: 'Bearer ' + apiKey, 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error('resend ' + res.status + ' ' + (await res.text()));
}

// FROM_EMAIL is shared with Model Intelligence and reads "yellow3 Model
// Intelligence <access@yellow3.io>". A supplier claiming their register profile
// should not hear from a subscription product they have never heard of, so we
// keep the verified sending address and put the register's name on it.
function senderFor(from) {
  if (process.env.CLAIM_FROM_EMAIL) return process.env.CLAIM_FROM_EMAIL;
  const m = String(from || '').match(/<([^>]+)>/);
  const addr = m ? m[1] : String(from || '').trim();
  return addr ? 'yellow3 DPP Supplier Register <' + addr + '>' : from;
}

// Every claim leaves a trace in the runtime log, whatever happens to the email.
// A claim is an inbound lead; losing one silently because a mail server hiccuped
// is not acceptable. `level` error makes failures show up in Vercel's error view.
function note(outcome, fields, failed) {
  const line = JSON.stringify(Object.assign({ evt: 'dpp_claim', outcome }, fields || {}));
  if (failed) console.error(line); else console.log(line);
}


// ---------------------------------------------------------------------------
// REPEAT CLAIMS
//
// TreVerum claimed on 30 July and again on 17 August. Nothing had failed; the
// first email arrived. They told us plainly why: "we weren't certain the first
// one had gone through, so we redid it just to be safe". The page cannot
// resolve that, and must not - saying "sent" would confirm a domain match and
// turn this form into a way to enumerate who works where.
//
// The email can. It is the one channel where the identity is already
// established, so it can say "you already have a live link" without telling
// anyone anything they did not already know.
//
// WHAT IS STORED, AND WHY IT LOOKS LIKE THIS. The blob store is PUBLIC. A record
// of "this address claimed this company" is exactly the kind of object the
// register must never publish, so nothing identifying is written: the pathname
// is an HMAC of (supplier, email) under AUTH_SECRET, and the body holds only
// timestamps and a count. Found by URL, it names nobody. No claims table -
// there is deliberately no account, queue or claim state in this design.
function lockKey(sid, email, secret) {
  return crypto.createHmac('sha256', String(secret))
    .update(sid + '|' + email).digest('hex');
}

// "14:32 UTC on 3 September 2026" - unambiguous to a reader in any timezone,
// which a bare clock time is not.
function untilText(ms) {
  const d = new Date(ms);
  const months = ['January', 'February', 'March', 'April', 'May', 'June', 'July',
    'August', 'September', 'October', 'November', 'December'];
  const hh = String(d.getUTCHours()).padStart(2, '0');
  const mm = String(d.getUTCMinutes()).padStart(2, '0');
  return hh + ':' + mm + ' UTC on ' + d.getUTCDate() + ' ' +
    months[d.getUTCMonth()] + ' ' + d.getUTCFullYear();
}

const ORDINAL = { 2: 'second', 3: 'third', 4: 'fourth', 5: 'fifth' };

const shell = inner =>
  '<div style="font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;max-width:520px;margin:0 auto;color:#0e0e0e">'
  + '<div style="height:4px;width:40px;background:#ffe000;margin-bottom:24px"></div>' + inner + '</div>';

const p = t => '<p style="font-size:15px;color:#4b4b4b;line-height:1.55;margin:0 0 18px">' + t + '</p>';

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

  if (!isEmail(email) || !id) { note('bad_input', { supplier: id }); return ok(); }

  const dom = domainOf(email);
  if (!dom || PUBLIC_MAILBOXES.has(dom)) { note('public_mailbox', { supplier: id, domain: dom }); return ok(); }

  // CLAIM_TEST_DOMAIN lets us prove the whole path end to end without faking an
  // alias in the register. Set it to a domain we control, test, then unset it.
  const TEST = String(process.env.CLAIM_TEST_DOMAIN || '').toLowerCase().trim();

  let row, matched = false;
  try {
    const rows = register();
    row = rows.find(r => r.id === id) || null;
    if (row) matched = ownedDomains(row).includes(dom) || (!!TEST && dom === TEST);
  } catch (e) {
    note('register_read_failed', { supplier: id, domain: dom, error: String(e && e.message || e) }, true);
    return ok();
  }
  if (!row) { note('unknown_supplier', { supplier: id, domain: dom }); return ok(); }

  const KEY = process.env.RESEND_API_KEY;
  const FROM = process.env.FROM_EMAIL;
  const NOTIFY = process.env.CLAIM_NOTIFY_EMAIL || FROM;
  const SENDER = senderFor(FROM);
  const url = SITE + '/research/digital-product-passport/suppliers/' + row.id;

  // A near miss is a lead, not a dead end. Somebody at a real company domain
  // went looking for their own profile and our row has the wrong domain, or a
  // subsidiary domain we never recorded. Tell ourselves so the row can be
  // resolved; the claimant sees exactly what a match sees, so this still cannot
  // be used to enumerate anything.
  if (!matched) {
    note('no_domain_match', { supplier: row.id, name: row.name, email: email, domain: dom, on_record: row.domain || '' });
    if (KEY && FROM && NOTIFY) {
      try {
        await send(KEY, SENDER, NOTIFY, 'Claim attempt, no domain match: ' + row.name,
          shell('<h1 style="font-size:18px;font-weight:800;margin:0 0 12px">' + row.name + '</h1>'
            + p('Someone tried to claim this profile from a domain we do not have on record. '
              + 'If they belong to this company, the row needs its domain corrected or the address '
              + 'added to <b>alias_domains</b>, and the claim will then work.')
            + '<p style="font-size:14px;color:#4b4b4b;line-height:1.6;margin:0">'
            + '<b>Wrote from:</b> ' + email + '<br>'
            + '<b>Their domain:</b> ' + dom + '<br>'
            + '<b>On record:</b> ' + (row.domain || 'none') + '<br>'
            + '<b>Row:</b> ' + row.id + '<br>'
            + '<b>Profile:</b> <a href="' + url + '">' + url + '</a></p>'), email);
        note('near_miss_notified', { supplier: row.id, to: NOTIFY });
      } catch (e) {
        note('near_miss_notify_failed', { supplier: row.id, email: email, error: String(e && e.message || e) }, true);
      }
    }
    return ok();
  }

  // Logged before any send, so a verified claim survives a missing key, a bad
  // address or a Resend outage.
  note('verified', { supplier: row.id, name: row.name, email: email, domain: dom, url: url });

  if (!KEY || !FROM) {
    note('not_configured', { supplier: row.id, email: email, missing: (!KEY ? 'RESEND_API_KEY ' : '') + (!FROM ? 'FROM_EMAIL' : '') }, true);
    return ok();
  }
  if (!process.env.AUTH_SECRET) {
    note('not_configured', { supplier: row.id, email: email, missing: 'AUTH_SECRET' }, true);
    return ok();
  }

  const token = sign({ k: 'dpp', sid: row.id, email: email, x: Date.now() + LINK_TTL_MS }, process.env.AUTH_SECRET);
  const link = SITE + '/api/claim-verify?t=' + encodeURIComponent(token);

  // Is a link from an earlier claim still live? Never fatal: if the store
  // cannot be read the claimant simply gets the ordinary email, which is the
  // behaviour that existed before this check.
  const now = Date.now();
  const lk = lockKey(row.id, email, process.env.AUTH_SECRET);
  let live = null;
  try {
    live = await claimlock.read(lk, now);
  } catch (e) {
    note('claim_lock_unreadable', { supplier: row.id, error: String(e && e.message || e) }, true);
  }

  // The FIRST link's issue time and expiry are what the notice reports, so they
  // are preserved across repeats rather than refreshed.
  const record = live
    ? { i: live.i, x: live.x, n: (live.n || 1) + 1 }
    : { i: now, x: now + LINK_TTL_MS, n: 1 };
  try {
    await claimlock.write(lk, record);
  } catch (e) {
    note('claim_lock_unwritable', { supplier: row.id, error: String(e && e.message || e) }, true);
  }

  let repeatNotice = '';
  if (live) {
    const mins = Math.max(1, Math.round((now - live.i) / 60000));
    const which = ORDINAL[record.n] || 'latest';
    // Counted, so the rate is measurable. A high rate means the page copy in
    // 3a is not doing its job and the wording needs another pass.
    note('repeat_claim', {
      supplier: row.id, email: email, claim_number: record.n,
      minutes_since_first: mins, first_expires: new Date(live.x).toISOString(),
    });
    repeatNotice = p('<b>You already have a working link.</b> This is the ' + which
      + ' link we have sent you for ' + row.name + ' in the last ' + mins + ' minute'
      + (mins === 1 ? '' : 's') + '. The first is still valid until ' + untilText(live.x)
      + '. Either will work; you do not need to claim again.');
  }

  // Us first, in its own try. It used to share one try/catch with the claimant
  // mail, in sequence, so an address our sender rejected also took out the
  // internal notification: the claim vanished twice over.
  if (NOTIFY) {
    try {
      await send(KEY, SENDER, NOTIFY, 'Profile claimed: ' + row.name,
        shell('<h1 style="font-size:18px;font-weight:800;margin:0 0 12px">' + row.name + '</h1>'
          + '<p style="font-size:14px;color:#4b4b4b;line-height:1.6;margin:0">'
          + '<b>Claimed by:</b> ' + email + '<br>'
          + '<b>Domain matched:</b> ' + dom + '<br>'
          + '<b>Row:</b> ' + row.id + '<br>'
          + '<b>Profile:</b> <a href="' + url + '">' + url + '</a></p>'
          + p('They can edit their own layer from here. No action needed.')), email);
      note('notified', { supplier: row.id, to: NOTIFY });
    } catch (e) {
      note('notify_failed', { supplier: row.id, to: NOTIFY, email: email, error: String(e && e.message || e) }, true);
    }
  } else {
    note('no_notify_address', { supplier: row.id, email: email }, true);
  }

  try {
    await send(KEY, SENDER, email, 'Your claim on the yellow3 DPP Supplier Register',
      shell(
        '<h1 style="font-size:20px;font-weight:800;letter-spacing:-0.02em;margin:0 0 12px">Claim confirmed for ' + row.name + '</h1>'
        + repeatNotice
        + p('We verified that you wrote from <b>' + dom + '</b>, the domain on record for this profile, so the claim is confirmed.')
        + p('The button below opens your profile editor. Add your logo, a one-line description, '
          + 'a contact link and your sectors. It publishes immediately, in its own layer, marked '
          + 'as supplied by you and dated.')
        + '<a href="' + link + '" style="display:inline-block;background:#0e0e0e;color:#fff;font-size:13px;font-weight:700;letter-spacing:0.06em;text-transform:uppercase;text-decoration:none;padding:15px 30px">Edit your profile &#8594;</a>'
        + '<p style="font-size:12px;color:#8a8a8a;line-height:1.5;margin:24px 0 0">This link is for you alone and works for 24 hours. Claim again any time to get a new one.</p>'
        + p('<br>What we verified independently stays as it is, with its source and the date we '
          + 'checked it. Company-supplied content never overwrites it. If something we published '
          + 'is wrong, reply with the correction and a source and we will check it, fix it and log '
          + 'the change.')
        + '<p style="font-size:12px;color:#8a8a8a;line-height:1.5;margin:28px 0 0">If you did not request this, you can ignore it. Nothing on the profile has changed.</p>'),
      NOTIFY || undefined);
    note('confirmed', { supplier: row.id, email: email });
  } catch (e) {
    note('confirm_failed', { supplier: row.id, email: email, error: String(e && e.message || e) }, true);
  }
  return ok();
};
