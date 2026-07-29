'use strict';
// GET /api/logo?id=<sid> -> the company's own logo.
//
// The blob store is private, so the file has no URL a browser can load. This
// streams it instead. The content is deliberately public - a logo a company
// supplied for display on its own public profile - so there is no session
// check here. The only thing this can ever return is a logo a verified claimant
// uploaded for that row.

const fs = require('fs');
const path = require('path');
const blob = require('./_lib/blob');

const EXT_TYPE = {
  png: 'image/png', jpg: 'image/jpeg', webp: 'image/webp', svg: 'image/svg+xml',
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

module.exports = async (req, res) => {
  const url = new URL(req.url, 'https://www.yellow3.io');
  const id = String(url.searchParams.get('id') || '').trim();
  if (!id || !knownId(id)) return res.status(404).end();

  let rec = null;
  try { rec = await blob.getJson('dpp/supplied/' + id + '.json'); } catch (e) {
    console.error(JSON.stringify({ evt: 'dpp_logo', outcome: 'record_unreadable', supplier: id, error: String(e && e.message || e) }));
    return res.status(502).end();
  }
  if (!rec || !rec.logo_path) return res.status(404).end();

  const ext = String(rec.logo_path).split('.').pop().toLowerCase();
  const type = EXT_TYPE[ext];
  if (!type) return res.status(404).end();

  try {
    const upstream = await blob.getRaw(rec.logo_path);
    if (!upstream) return res.status(404).end();
    const buf = Buffer.from(await upstream.arrayBuffer());
    res.setHeader('Content-Type', type);
    // short cache: a company that replaces its mark should see it change
    res.setHeader('Cache-Control', 'public, max-age=300');
    return res.status(200).send(buf);
  } catch (e) {
    console.error(JSON.stringify({ evt: 'dpp_logo', outcome: 'stream_failed', supplier: id, error: String(e && e.message || e) }));
    return res.status(502).end();
  }
};
