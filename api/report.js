'use strict';
// GET /api/report -> streams the current paid report PDF, but only to a
// signed-in subscriber. The file lives in PRIVATE storage (Vercel Blob); its
// URL is in REPORT_URL and is never exposed publicly. This is what actually
// gates the paid report: without a valid session the bytes are never served,
// and the file is not in the public repo or on any public path.
// Zero-dependency: Node built-ins + global fetch (Node 18+ on Vercel).
const { verify, parseCookies } = require('./_lib/util');

module.exports = async (req, res) => {
  res.setHeader('Cache-Control', 'private, no-store');

  // 1) require a valid session
  const cookies = parseCookies(req.headers.cookie || '');
  const data = verify(cookies['y3mi'] || '', process.env.AUTH_SECRET);
  if (!data) {
    res.writeHead(302, { Location: '/research/model-adoption/login' });
    res.end();
    return;
  }

  // 2) fetch the report from private storage and stream it back
  const src = process.env.REPORT_URL;
  if (!src) { res.status(503).json({ error: 'report_not_configured' }); return; }
  try {
    const headers = {};
    if (process.env.BLOB_READ_WRITE_TOKEN) {
      headers.Authorization = 'Bearer ' + process.env.BLOB_READ_WRITE_TOKEN;
    }
    const upstream = await fetch(src, { headers });
    if (!upstream.ok) throw new Error('upstream ' + upstream.status);
    const buf = Buffer.from(await upstream.arrayBuffer());
    res.setHeader('Content-Type', 'application/pdf');
    res.setHeader('Content-Disposition', 'inline; filename="yellow3-model-adoption-report.pdf"');
    res.status(200).send(buf);
  } catch (e) {
    console.error('report', e);
    res.status(502).json({ error: 'report_unavailable' });
  }
};
