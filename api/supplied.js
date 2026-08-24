'use strict';
// The company-supplied layer.
//
//   GET  /api/supplied?id=<sid>   public. What the company says about itself.
//   POST /api/supplied            the company edits its own layer. Requires the
//                                 y3dpp session, and only for its own row.
//
// This layer NEVER touches anything yellow3 verified. The verified fields live
// in research/dpp-suppliers.json, are built into the static page, and are not
// writable from here at all - there is no code path from this endpoint to them.

const fs = require('fs');
const path = require('path');
const { verify, parseCookies } = require('./_lib/util');
const blob = require('./_lib/blob');

const MAX_LOGO_BYTES = 400 * 1024;
const LOGO_TYPES = {
  'image/png': 'png', 'image/jpeg': 'jpg', 'image/webp': 'webp', 'image/svg+xml': 'svg',
};

let IDS = null;
function knownId(id) {
  if (!IDS) {
    const p = path.join(process.cwd(), 'research', 'dpp-suppliers.json');
    const rows = JSON.parse(fs.readFileSync(p, 'utf8')).suppliers || [];
    IDS = new Set(rows.map(r => r.id));
  }
  return IDS.has(id);
}

const keyFor = sid => 'dpp/supplied/' + sid + '.json';

// A company that clears everything is unclaimed again, not "claimed with
// nothing to say". Without this a cleared profile would still announce a
// supplied layer and date it, which is a claim about the company that the
// company did not make.
function isEmpty(rec) {
  return !rec || (!rec.logo_url && !rec.description && !rec.contact_url
    && !(rec.sectors && rec.sectors.length));
}
// One small index so the directory can show 183 rows without 183 requests.
// Rewritten on every save; at a handful of claims a day a lost-update race is
// not worth a lock, and the per-supplier record above stays authoritative.
const INDEX = 'dpp/supplied/_index.json';

// Plain text only. Everything here is rendered with textContent on the page, but
// strip anyway so nothing tag-shaped is ever stored under our name.
function text(v, max) {
  return String(v == null ? '' : v)
    .replace(/<[^>]*>/g, '')
    .replace(/[\x00-\x1f\x7f]/g, ' ')
    .trim()
    .slice(0, max);
}

// The domain of a work address, and nothing else. Returns '' rather than a
// partial when the input is not an address, because half an identifier in a
// public record is worse than none.
function domainOf(email) {
  const at = String(email || '').lastIndexOf('@');
  return at > 0 ? String(email).slice(at + 1).toLowerCase() : '';
}

// DISPLAY TEXT, WHICH MUST NEVER BE PUBLISHED MID-WORD.
//
// `text` hard-slices, which is correct for a URL and wrong for a label a person
// typed. On 2026-08-24 Repass saved the sector "Consumer goods wholesales &
// retail" - 33 characters against a 30 cap - and the register published
// "Consumer goods wholesales & re" on their public profile, under their own
// name, in the layer marked as supplied by them. The editor input carried no
// length limit either, so nothing told them it had happened.
//
// Cut at the last word boundary instead. A single word longer than the whole
// allowance still gets a hard cut - there is nowhere else to break it - but the
// common case now ends on a word. The cap still exists: this is about how it
// truncates, not whether it does.
function label(v, max) {
  const s = text(v, max + 1);          // one over the cap, so overflow is visible
  if (s.length <= max) return s;
  const cut = s.slice(0, max);
  const sp = cut.lastIndexOf(' ');
  return (sp > max / 2 ? cut.slice(0, sp) : cut).trim();
}

function httpsUrl(v) {
  const s = text(v, 300);
  if (!s) return '';
  try {
    const u = new URL(s);
    return u.protocol === 'https:' ? u.toString() : '';
  } catch (e) { return ''; }
}

function session(req) {
  const c = parseCookies(req.headers.cookie || '');
  const d = verify(c['y3dpp'] || '', process.env.AUTH_SECRET);
  return (d && d.k === 'dpp-session' && d.sid) ? d : null;
}

module.exports = async (req, res) => {
  res.setHeader('Cache-Control', 'no-store');

  if (req.method === 'GET') {
    const url = new URL(req.url, 'https://www.yellow3.io');
    const id = String(url.searchParams.get('id') || '').trim();
    if (url.searchParams.get('all')) {
      let idx = null;
      try { idx = await blob.getJson(INDEX); } catch (e) { console.error('supplied index', e); }
      return res.status(200).json({ supplied: idx || {} });
    }
    if (!id || !knownId(id)) return res.status(200).json({ supplied: null });
    const s = session(req);
    let supplied = null;
    try { supplied = await blob.getJson(keyFor(id)); } catch (e) { console.error('supplied get', e); }
    if (isEmpty(supplied)) supplied = null;
    return res.status(200).json({ supplied: supplied, editable: !!(s && s.sid === id) });
  }

  if (req.method !== 'POST') {
    res.setHeader('Allow', 'GET, POST');
    return res.status(405).json({ ok: false });
  }

  const s = session(req);
  if (!s) return res.status(401).json({ ok: false, error: 'not_signed_in' });

  let body = req.body;
  if (typeof body === 'string') { try { body = JSON.parse(body); } catch (e) { body = {}; } }
  body = body || {};

  // A session authorises exactly one row. The id in the payload is ignored.
  const sid = s.sid;
  if (!knownId(sid)) return res.status(400).json({ ok: false, error: 'unknown_supplier' });

  let current = null;
  try { current = await blob.getJson(keyFor(sid)); } catch (e) { current = null; }

  const now = new Date().toISOString().slice(0, 10);
  const rec = {
    supplier_id: sid,
    description: label(body.description, 160),
    contact_url: httpsUrl(body.contact_url),
    // 48, not 30. A real sector label - "Consumer goods wholesales & retail" -
    // is 33 characters and did not fit. Eight of these is still bounded.
    sectors: Array.isArray(body.sectors)
      ? body.sectors.map(t => label(t, 48)).filter(Boolean).slice(0, 8) : [],
    logo_path: (current && current.logo_path) || '',
    logo_url: (current && current.logo_url) || '',
    licence: (current && current.licence) || null,
    updated_at: now,
    // THE DOMAIN, NEVER THE PERSON. This record is served from the PUBLIC blob
    // store, so `updated_by: s.email` published a named individual's work
    // address - "sammy.williamson@..." - to anyone with the URL, for every
    // company that has claimed a profile.
    //
    // The domain carries the whole audit property without the person. Claiming
    // already REQUIRES a work email matching the domain that defines the row
    // (api/claim.js), so "someone at rosellastreet.com did this" is exactly
    // what the address proved, and the local part proved nothing extra.
    updated_by_domain: domainOf(s.email),
    first_supplied_at: (current && current.first_supplied_at) || now,
  };

  // Logo. The company warrants it owns the mark and grants us display rights at
  // the moment of upload - which is the cleanest provenance available and the
  // reason we never source, redraw or recolour a mark ourselves.
  if (body.logo && body.logo.data) {
    if (body.licence !== true) {
      return res.status(400).json({ ok: false, error: 'licence_required' });
    }
    const type = String(body.logo.contentType || '').toLowerCase();
    const ext = LOGO_TYPES[type];
    if (!ext) return res.status(400).json({ ok: false, error: 'logo_type' });
    let buf;
    try {
      buf = Buffer.from(String(body.logo.data).replace(/^data:[^,]*,/, ''), 'base64');
    } catch (e) { return res.status(400).json({ ok: false, error: 'logo_unreadable' }); }
    if (!buf.length || buf.length > MAX_LOGO_BYTES) {
      return res.status(400).json({ ok: false, error: 'logo_size' });
    }
    try {
      const p = 'dpp/logos/' + sid + '.' + ext;
      await blob.put(p, buf, type, 300);
      rec.logo_path = p;
      // the browser loads the logo through our own endpoint rather than a direct
      // blob URL. NOTE, corrected 2026-08-21: this comment used to say "the
      // store is private". It is not - dpp/supplied/ and dpp/suggestions/ are
      // served to anyone with the URL, which is how a named individual's address
      // came to be published. Verification standard rule 7: a permission and the
      // comment defending it have to be checked together.
      // the stamp busts the CDN cache when a company replaces its mark.
      rec.logo_url = '/api/logo?id=' + encodeURIComponent(sid) + '&v=' + Date.now();
      // Same rule as updated_by_domain above: the licence needs to show that a
      // person AT THAT COMPANY granted display rights, not which person.
      rec.licence = { granted_by_domain: domainOf(s.email), granted_at: now,
                      warrant: 'owner_or_authorised' };
    } catch (e) {
      console.error(JSON.stringify({ evt: 'dpp_supplied', outcome: 'logo_store_failed', supplier: sid, error: String(e && e.message || e) }));
      return res.status(502).json({ ok: false, error: 'logo_store_failed' });
    }
  }

  if (body.remove_logo === true) { rec.logo_url = ''; rec.logo_path = ''; rec.licence = null; }

  try {
    await blob.putJson(keyFor(sid), rec);
  } catch (e) {
    console.error(JSON.stringify({ evt: 'dpp_supplied', outcome: 'store_failed', supplier: sid, error: String(e && e.message || e) }));
    return res.status(502).json({ ok: false, error: 'store_failed' });
  }

  // keep the directory index in step; a failure here must not lose the save
  try {
    const idx = (await blob.getJson(INDEX)) || {};
    if (!isEmpty(rec)) {
      idx[sid] = { logo_url: rec.logo_url, description: rec.description, updated_at: rec.updated_at };
    } else {
      delete idx[sid];
    }
    await blob.putJson(INDEX, idx);
  } catch (e) {
    console.error(JSON.stringify({ evt: 'dpp_supplied', outcome: 'index_update_failed', supplier: sid, error: String(e && e.message || e) }));
  }

  console.log(JSON.stringify({ evt: 'dpp_supplied', outcome: 'saved', supplier: sid, by: s.email || '', has_logo: !!rec.logo_url }));
  return res.status(200).json({ ok: true, supplied: rec });
};
