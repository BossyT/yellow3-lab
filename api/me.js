'use strict';
// GET /api/me -> { authed, email, tier } from the session cookie. Used by the
// access page to gate content client-side.
const { verify, parseCookies } = require('./_lib/util');

module.exports = async (req, res) => {
  res.setHeader('Cache-Control', 'no-store');
  const cookies = parseCookies(req.headers.cookie || '');
  const data = verify(cookies['y3mi'] || '', process.env.AUTH_SECRET);
  if (!data) { res.status(200).json({ authed: false }); return; }
  res.status(200).json({ authed: true, email: data.e, tier: data.t });
};
