'use strict';
// Suggest a supplier for the register.
//
// A submission is a RESEARCH LEAD, never a listing. Nothing here creates a row
// or publishes anything. A company enters the register when we can source it
// from public evidence ourselves - that is the whole asset, and a form that
// wrote straight into the register would destroy it.
//
// Two fields: company name and work email. The domain comes from the email, so
// nobody types it twice and it cannot be a personal mailbox.
//
// Zero-dependency: Node built-ins + global fetch, same as the rest of /api.

const fs = require('fs');
const path = require('path');
const { domainOf, isEmail } = require('./_lib/util');
const blob = require('./_lib/blob');

const PUBLIC_MAILBOXES = new Set([
  'gmail.com', 'googlemail.com', 'outlook.com', 'hotmail.com', 'live.com',
  'yahoo.com', 'yahoo.co.uk', 'icloud.com', 'me.com', 'mac.com', 'aol.com',
  'proton.me', 'protonmail.com', 'gmx.com', 'gmx.net', 'msn.com', 'yandex.com',
  'zoho.com', 'fastmail.com', 'hey.com',
]);

const SITE = 'https://www.yellow3.io';
const BASE = SITE + '/research/digital-product-passport/suppliers/';

let REGISTER = null;
function register() {
  if (!REGISTER) {
    const p = path.join(process.cwd(), 'research', 'dpp-suppliers.json');
    REGISTER = JSON.parse(fs.readFileSync(p, 'utf8')).suppliers || [];
  }
  return REGISTER;
}

// domain first, then alias_domains - a company can already be in the register
// under a name it would not recognise, or as a parent it does not think of.
//
// The second return value matters for privacy. A supplier's `domain` is already
// published in the directory, so telling the browser "this one is already
// recorded" reveals nothing anyone could not read off the register. Its
// `alias_domains` are NOT published, so an alias match is never disclosed in the
// response - it is answered by email instead, which only reaches an address at
// that domain.
function findByDomain(dom) {
  var rows = register();
  var direct = rows.find(r => String(r.domain || '').toLowerCase() === dom);
  if (direct) return [direct, 'domain'];
  var alias = rows.find(function (r) {
    return String(r.alias_domains || '').split(',')
      .map(s => s.trim().toLowerCase()).filter(Boolean).includes(dom);
  });
  return alias ? [alias, 'alias'] : [null, ''];
}

function note(outcome, fields, failed) {
  const line = JSON.stringify(Object.assign({ evt: 'dpp_suggest', outcome }, fields || {}));
  if (failed) console.error(line); else console.log(line);
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

function senderFor(from) {
  if (process.env.CLAIM_FROM_EMAIL) return process.env.CLAIM_FROM_EMAIL;
  const m = String(from || '').match(/<([^>]+)>/);
  const addr = m ? m[1] : String(from || '').trim();
  return addr ? 'yellow3 DPP Supplier Register <' + addr + '>' : from;
}

const shell = inner =>
  '<div style="font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;max-width:520px;margin:0 auto;color:#0e0e0e">'
  + '<div style="height:4px;width:40px;background:#ffe000;margin-bottom:24px"></div>' + inner + '</div>';

const p = t => '<p style="font-size:15px;color:#4b4b4b;line-height:1.55;margin:0 0 18px">' + t + '</p>';
const btn = (href, label) =>
  '<a href="' + href + '" style="display:inline-block;background:#0e0e0e;color:#fff;font-size:13px;'
  + 'font-weight:700;letter-spacing:0.06em;text-transform:uppercase;text-decoration:none;padding:15px 30px">'
  + label + '</a>';

function text(v, max) {
  return String(v == null ? '' : v).replace(/<[^>]*>/g, '').replace(/[\x00-\x1f\x7f]/g, ' ').trim().slice(0, max);
}

module.exports = async (req, res) => {
  if (req.method !== 'POST') {
    res.setHeader('Allow', 'POST');
    return res.status(405).json({ ok: false });
  }

  let body = req.body;
  if (typeof body === 'string') { try { body = JSON.parse(body); } catch (e) { body = {}; } }
  const email = String((body && body.email) || '').toLowerCase().trim();
  const name = text(body && body.company, 120);

  // One answer for every path. The form must not become a way to test which
  // companies we already hold.
  const ok = () => res.status(200).json({ ok: true });

  if (!isEmail(email) || !name) { note('bad_input'); return ok(); }

  const dom = domainOf(email);
  if (!dom || PUBLIC_MAILBOXES.has(dom)) { note('public_mailbox', { domain: dom }); return ok(); }

  const KEY = process.env.RESEND_API_KEY;
  const FROM = process.env.FROM_EMAIL;
  const NOTIFY = process.env.CLAIM_NOTIFY_EMAIL || FROM;
  const SENDER = senderFor(FROM);

  let existing = null, matchedOn = '';
  try { [existing, matchedOn] = findByDomain(dom); } catch (e) {
    note('register_read_failed', { domain: dom, error: String(e && e.message || e) }, true);
  }

  // Already in the register, very likely under a name they do not recognise.
  // This is the most useful outcome of the whole form: it turns "please add us"
  // into a claim, at no cost to anyone.
  if (existing) {
    note('already_listed', { domain: dom, supplier: existing.id, submitted_as: name,
                             email: email, matched_on: matchedOn });
    if (KEY && FROM) {
      try {
        await send(KEY, SENDER, email, 'You are already in the yellow3 DPP Supplier Register',
          shell('<h1 style="font-size:20px;font-weight:800;letter-spacing:-0.02em;margin:0 0 12px">'
            + existing.name + ' is already recorded</h1>'
            + p('We already hold a profile for <b>' + dom + '</b>, recorded as <b>' + existing.name
              + '</b>. You may not recognise the name we researched it under.')
            + p('You can claim it from the same work address you used here, and add your logo, '
              + 'a description, a contact link and your sectors. What we researched independently '
              + 'stays as it is, with its source and date.')
            + btn(BASE + existing.id + '/claim', 'Claim your profile &#8594;')
            + '<p style="font-size:12px;color:#8a8a8a;line-height:1.5;margin:28px 0 0">'
            + 'If something we published is wrong, reply with the correction and a source and we '
            + 'will check it, fix it and log the change.</p>'), NOTIFY || undefined);
      } catch (e) { note('reply_failed', { domain: dom, error: String(e && e.message || e) }, true); }
    }
    if (matchedOn === 'domain') {
      return res.status(200).json({ ok: true, existing: {
        id: existing.id, name: existing.name,
        claim_url: '/research/digital-product-passport/suppliers/' + existing.id + '/claim',
      } });
    }
    return ok();
  }

  // New to us. Queue it as research, and say plainly that a submission is not a
  // listing. Deduped by domain: submitting twice updates one record.
  const now = new Date().toISOString().slice(0, 10);
  const rec = { domain: dom, company: name, email: email, submitted_at: now, status: 'queued' };
  try {
    const prev = await blob.getJson('dpp/suggestions/' + dom + '.json');
    if (prev && prev.submitted_at) rec.submitted_at = prev.submitted_at;
    rec.last_seen = now;
    await blob.putJson('dpp/suggestions/' + dom + '.json', rec);
    note('queued', { domain: dom, company: name, email: email, repeat: !!prev });
  } catch (e) {
    // the notification below still reaches a human, so the lead is not lost
    note('queue_failed', { domain: dom, company: name, email: email, error: String(e && e.message || e) }, true);
  }

  if (!KEY || !FROM) { note('not_configured', { domain: dom }, true); return ok(); }

  if (NOTIFY) {
    try {
      await send(KEY, SENDER, NOTIFY, 'Suggested for the register: ' + name,
        shell('<h1 style="font-size:18px;font-weight:800;margin:0 0 12px">' + name + '</h1>'
          + '<p style="font-size:14px;color:#4b4b4b;line-height:1.6;margin:0">'
          + '<b>Domain:</b> ' + dom + '<br>'
          + '<b>From:</b> ' + email + '<br>'
          + '<b>In the register:</b> no match on domain or alias</p>'
          + p('Queued for the next research pass. Nothing has been published.')), email);
      note('notified', { domain: dom, to: NOTIFY });
    } catch (e) {
      note('notify_failed', { domain: dom, error: String(e && e.message || e) }, true);
    }
  }

  try {
    await send(KEY, SENDER, email, 'Received: ' + name + ' for the DPP Supplier Register',
      shell('<h1 style="font-size:20px;font-weight:800;letter-spacing:-0.02em;margin:0 0 12px">'
        + 'We have your suggestion</h1>'
        + p('<b>' + name + '</b> (' + dom + ') is queued for the next research pass.')
        + p('One thing to be straight about: a suggestion is not a listing. We add a company '
          + 'only when we can establish it from public evidence ourselves, and every field we '
          + 'publish carries its source and the date we checked it. That is the whole point of '
          + 'the register, and it is why being in it means something.')
        + p('What helps most, if you have it: a public product page describing your Digital '
          + 'Product Passport capability, technical documentation, or a named customer pilot. '
          + 'Reply to this email with links and it goes into the research record.')
        + p('If we can source you, you will appear with your headquarters, entity type and '
          + 'evidence, and you can then claim the profile and add your own layer. If we cannot, '
          + 'we will tell you what was missing.')
        + '<p style="font-size:12px;color:#8a8a8a;line-height:1.5;margin:28px 0 0">'
        + 'We never charge to be listed, and we never sell verification.</p>'),
      NOTIFY || undefined);
    note('acknowledged', { domain: dom });
  } catch (e) {
    note('ack_failed', { domain: dom, error: String(e && e.message || e) }, true);
  }

  return ok();
};
