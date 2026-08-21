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

const fs = require('fs');
const path = require('path');
const blob = require('./_lib/blob');

// A domain that cannot be an external company waiting for an answer.
//
// WHY THIS EXISTS, and it is not a loosened threshold. On 21 August 2026 the
// build had been refusing every deploy for three days because "a company has
// been waiting 22 days". Read from the store, the three queued submissions
// were: yellow3.io - OUR OWN domain, submitted as a test - a probe on
// `a-company-not-in-register.test`, and treverum.com, which is already in the
// register. So the count of companies waiting for an answer was two, and the
// number of companies waiting for an answer was zero. Meanwhile production sat
// on a three-day-old build showing a "Live" badge over 18 August data.
//
// The 21-day threshold is untouched. What changes is what counts as a company.
// `.test`, `.example`, `.invalid` and `.localhost` are reserved by RFC 2606 and
// RFC 6761 and are unroutable - nobody can receive a reply there - and our own
// domain is us. Neither can ever be somebody waiting.
//
// COUNTED AND REPORTED, NEVER SILENTLY DROPPED. A submission excluded here
// appears as `not_a_company` in the response, so a real company can never be
// quietly discarded by a rule meant for fixtures.
const RESERVED_TLDS = ['.test', '.example', '.invalid', '.localhost'];
const OUR_DOMAINS = ['yellow3.io', 'buyer.yellow3.io', 'naffe.ai'];
function notACompany(dom) {
  if (OUR_DOMAINS.includes(dom)) return true;
  if (OUR_DOMAINS.some((d) => dom.endsWith('.' + d))) return true;
  if (RESERVED_TLDS.some((t) => dom.endsWith(t))) return true;
  return ['example.com', 'example.net', 'example.org'].includes(dom);
}

// The register's own domains, so a queued submission can be told apart from a
// company that is already listed. Without this the count is misleading: a
// submission whose status was never closed after the company was added reads
// exactly like a company nobody has answered.
function knownDomains() {
  try {
    const p = path.join(process.cwd(), 'research', 'dpp-suppliers.json');
    const rows = JSON.parse(fs.readFileSync(p, 'utf8')).suppliers || [];
    const set = new Set();
    for (const r of rows) {
      for (const d of [r.domain].concat(String(r.alias_domains || '').split(','))) {
        const v = String(d || '').trim().toLowerCase().replace(/^www\./, '');
        if (v) set.add(v);
      }
    }
    return set;
  } catch (e) {
    return null;
  }
}

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
    const known = knownDomains();
    const byStatus = {};
    const ages = [];
    let undated = 0;
    let alreadyListed = 0;
    let notCompany = 0;
    let awaitingResearch = 0;

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
      const dom = String((item && item.domain) || name.slice(PREFIX.length))
        .replace(/\.json$/, '').trim().toLowerCase().replace(/^www\./, '');
      if (notACompany(dom)) {
        // Our own domain or a reserved, unroutable one. Not a company, so it
        // cannot be a company waiting. Counted so it stays visible.
        notCompany += 1;
        continue;
      }
      const listed = known ? known.has(dom) : false;
      if (listed) {
        // In the register already. The submission's status was simply never
        // closed - bookkeeping, not a company waiting for an answer.
        alreadyListed += 1;
        continue;
      }
      awaitingResearch += 1;
      const age = item && item.submitted_at ? days(item.submitted_at, now) : null;
      if (age === null) undated += 1;
      else ages.push(age);
    }

    res.setHeader('content-type', 'application/json');
    return res.end(JSON.stringify({
      generated: new Date().toISOString().slice(0, 10),
      total: blobs.filter((b) => String(b.pathname || '').startsWith(PREFIX)).length,
      queued: byStatus.queued || 0,
      awaiting_research: awaitingResearch,
      already_listed_not_closed: alreadyListed,
      not_a_company: notCompany,
      register_read: known ? known.size : null,
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
