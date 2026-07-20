'use strict';
// GET /api/auth/verify?token=... -> validate the magic token, set a 30-day
// signed session cookie, and redirect into the access page.
const { verify, sign, cookie } = require('../_lib/util');

module.exports = async (req, res) => {
  const token = (req.query && req.query.token) || '';
  const data = verify(token, process.env.AUTH_SECRET);
  if (!data) {
    res.writeHead(302, { Location: '/research/model-adoption/login?e=expired' });
    res.end();
    return;
  }
  const session = sign({ e: data.e, t: data.t, x: Date.now() + 30 * 24 * 3600 * 1000 }, process.env.AUTH_SECRET);
  res.setHeader('Set-Cookie', cookie('y3mi', session, 30 * 24 * 3600));
  res.writeHead(302, { Location: '/research/model-adoption/access?tier=' + encodeURIComponent(data.t) });
  res.end();
};
