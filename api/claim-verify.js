'use strict';
// GET /api/claim-verify?t=... -> exchange the emailed claim link for a session
// scoped to ONE supplier row, then drop the visitor into their editor.
//
// The session says nothing about yellow3 access. It authorises editing the
// company-supplied layer of a single profile and nothing else.

const { verify, sign, cookie } = require('./_lib/util');

const SESSION_DAYS = 30;
const BASE = '/research/digital-product-passport/suppliers/';

module.exports = async (req, res) => {
  const url = new URL(req.url, 'https://www.yellow3.io');
  const token = url.searchParams.get('t') || '';
  const secret = process.env.AUTH_SECRET;

  const data = secret ? verify(token, secret) : null;
  if (!data || data.k !== 'dpp' || !data.sid) {
    console.log(JSON.stringify({ evt: 'dpp_claim', outcome: 'link_rejected' }));
    res.writeHead(302, { Location: BASE + '?expired=1' });
    return res.end();
  }

  const session = sign(
    { k: 'dpp-session', sid: data.sid, email: data.email, x: Date.now() + SESSION_DAYS * 864e5 },
    secret);

  console.log(JSON.stringify({ evt: 'dpp_claim', outcome: 'editor_opened', supplier: data.sid, email: data.email }));
  res.setHeader('Set-Cookie', cookie('y3dpp', session, SESSION_DAYS * 86400));
  res.writeHead(302, { Location: BASE + encodeURIComponent(data.sid) + '/edit' });
  res.end();
};
