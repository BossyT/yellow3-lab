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

// Plain text only. Everything here is rendered with textContent on the page, but
// strip anyway so nothing tag-shaped is ever stored under our name.
function text(v, max) {
  return String(v == null ? '' : v)
    .replace(/<[^>]*>/g, '')
    .replace(/[\x00-\x1f\x7f]/g, ' ')
    .trim()
    .slice(0, max);
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
    if (!id || !knownId(id)) return res.status(200).json({ supplied: null });
    const s = session(req);
    let supplied = null;
    try { supplied = await blob.getJson(keyFor(id)); } catch (e) { console.error('supplied get', e); }
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
    description: text(body.description, 160),
    contact_url: httpsUrl(body.contact_url),
    sectors: Array.isArray(body.sectors)
      ? body.sectors.map(t => text(t, 30)).filter(Boolean).slice(0, 8) : [],
    logo_url: (current && current.logo_url) || '',
    licence: (current && current.licence) || null,
    updated_at: now,
    updated_by: s.email || '',
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
      const up = await blob.put('dpp/logos/' + sid + '.' + ext, buf, type, 300);
      rec.logo_url = up.url || blob.publicUrl('dpp/logos/' + sid + '.' + ext);
      rec.licence = { granted_by: s.email || '', granted_at: now, warrant: 'owner_or_authorised' };
    } catch (e) {
      console.error(JSON.stringify({ evt: 'dpp_supplied', outcome: 'logo_store_failed', supplier: sid, error: String(e && e.message || e) }));
      return res.status(502).json({ ok: false, error: 'logo_store_failed' });
    }
  }

  if (body.remove_logo === true) { rec.logo_url = ''; rec.licence = null; }

  try {
    await blob.putJson(keyFor(sid), rec);
  } catch (e) {
    console.error(JSON.stringify({ evt: 'dpp_supplied', outcome: 'store_failed', supplier: sid, error: String(e && e.message || e) }));
    return res.status(502).json({ ok: false, error: 'store_failed' });
  }

  console.log(JSON.stringify({ evt: 'dpp_supplied', outcome: 'saved', supplier: sid, by: s.email || '', has_logo: !!rec.logo_url }));
  return res.status(200).json({ ok: true, supplied: rec });
};
