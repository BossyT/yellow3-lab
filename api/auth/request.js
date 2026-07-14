'use strict';
// POST { email } -> if the address is covered by an active subscription
// (exact match, or Team company-domain), email a one-time magic link.
// Always returns a generic 200 so the endpoint cannot be used to enumerate
// who is or is not a subscriber.
const { sign, tierForEmail, sendMagic, isEmail } = require('../_lib/util');

module.exports = async (req, res) => {
  if (req.method !== 'POST') { res.status(405).json({ error: 'method_not_allowed' }); return; }

  let body = req.body;
  if (typeof body === 'string') { try { body = JSON.parse(body); } catch (e) { body = {}; } }
  const email = ((body && body.email) || '').toString().toLowerCase().trim();

  const generic = { ok: true, message: 'If your subscription covers that address, a sign-in link is on its way.' };
  res.setHeader('Cache-Control', 'no-store');
  if (!isEmail(email)) { res.status(200).json(generic); return; }

  try {
    const tier = await tierForEmail(email, process.env.STRIPE_SECRET_KEY);
    if (tier) {
      const token = sign({ e: email, t: tier, x: Date.now() + 15 * 60 * 1000 }, process.env.AUTH_SECRET);
      const host = req.headers['x-forwarded-host'] || req.headers.host;
      const proto = req.headers['x-forwarded-proto'] || 'https';
      const link = proto + '://' + host + '/api/auth/verify?token=' + encodeURIComponent(token);
      const from = process.env.FROM_EMAIL || 'yellow3 Model Intelligence <access@yellow3.io>';
      await sendMagic(email, link, process.env.RESEND_API_KEY, from);
    }
  } catch (e) {
    console.error('auth/request', e);
  }
  res.status(200).json(generic);
};
