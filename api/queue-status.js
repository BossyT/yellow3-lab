'use strict';
// GET /api/queue-status - how many register submissions are waiting, and how long.
//
// WHY THIS EXISTS. The register accepts submissions all day: the add page is
// live, api/suggest.js queues them, and the company gets a confirmation. The
// intake runbook says a scheduled agent turns those into rows. Nothing
// scheduled it, and on 16 August 2026 nobody could say whether anything was
// waiting, because nothing looked. A company that submitted and heard nothing
// is a worse failure than a slow queue, and the buyer platform reads this data.
//
// It runs HERE rather than in a workflow because the Blob token already exists
// in this environment. A GitHub job would have needed the secret copied across
// by hand, and the point of this is that nobody has to do anything.
//
// COUNTS AND AGES ONLY. No domains, no company names, no addresses. The runbook
// is explicit that companies which were not recorded are told privately and
// never appear on a public list, and this response is public and gets committed
// to the repo. Knowing WHICH company is a deliberate extra step: read the store.

const blob = require('./_lib/blob');

const PREFIX = 'dpp/suggestions/';

function days(fromIso, now) {
  const t = Date.parse(String(fromIso).slice(0, 10));
  if (Number.isNaN(t)) return null;
  return Math.floor((now - t) / 86400000);
}

module.exports = async (req, res) => {
  res.setHeader('cache-control', 'public, max-age=300');
  if (req.method !== 'GET') {
    res.statusCode = 405;
    return res.end(JSON.stringify({ error: 'GET only' }));
  }
  try {
    const now = Date.now();
    const blobs = await blob.list(PREFIX);
    const byStatus = {};
    const ages = [];
    let undated = 0;

    for (const b of blobs) {
      const name = String(b.pathname || '');
      if (!name.startsWith(PREFIX)) continue;
      let item = null;
      try {
        item = await blob.getJson(name);
      } catch (e) {
        item = null;
      }
      const status = String((item && item.status) || 'unreadable').toLowerCase();
      byStatus[status] = (byStatus[status] || 0) + 1;
      if (status !== 'queued') continue;
      const age = item && item.submitted_at ? days(item.submitted_at, now) : null;
      if (age === null) undated += 1;
      else ages.push(age);
    }

    res.setHeader('content-type', 'application/json');
    return res.end(JSON.stringify({
      generated: new Date().toISOString().slice(0, 10),
      total: blobs.filter((b) => String(b.pathname || '').startsWith(PREFIX)).length,
      queued: byStatus.queued || 0,
      oldest_queued_days: ages.length ? Math.max.apply(null, ages) : null,
      undated_queued: undated,
      by_status: byStatus,
    }));
  } catch (e) {
    // Say plainly that the queue could not be read. Reporting zero here would
    // be the same silence this endpoint exists to end.
    res.statusCode = 503;
    res.setHeader('content-type', 'application/json');
    return res.end(JSON.stringify({ error: 'queue unreadable', detail: String(e.message || e) }));
  }
};
