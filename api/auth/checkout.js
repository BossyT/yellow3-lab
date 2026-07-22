'use strict';
// GET /api/auth/checkout?session_id=cs_...
// Sign a buyer in straight from the Stripe Checkout redirect - no email round-trip.
// The redirect URL carries a Checkout Session id that only the buyer has; we verify
// it against Stripe (complete + paid + recent), confirm the email still maps to an
// ACTIVE subscription, then set the same 30-day session cookie the magic link sets.
// This makes purchase -> access self-serve even if email delivery is unavailable.
// Zero-dependency (Node built-ins + global fetch).
const { sign, cookie, tierForEmail } = require('../_lib/util');

async function stripeGet(path, key) {
  const res = await fetch('https://api.stripe.com/v1/' + path, {
    headers: { Authorization: 'Bearer ' + key },
  });
  if (!res.ok) throw new Error('stripe ' + res.status + ' ' + (await res.text()));
  return res.json();
}

module.exports = async (req, res) => {
  res.setHeader('Cache-Control', 'no-store');
  const sid = (req.query && req.query.session_id) || '';
  // On any failure, fall back to the email sign-in (welcome variant).
  const fallback = function () {
    res.writeHead(302, { Location: '/research/model-adoption/login?welcome=1' });
    res.end();
  };
  if (!/^cs_[A-Za-z0-9_]+$/.test(sid)) { fallback(); return; }

  try {
    const key = process.env.STRIPE_SECRET_KEY;
    const s = await stripeGet('checkout/sessions/' + encodeURIComponent(sid), key);

    const complete = s.status === 'complete' &&
      (s.payment_status === 'paid' || s.payment_status === 'no_payment_required');
    // anti-replay hygiene: a completed session id is only good for a day.
    const recent = s.created && (Date.now() / 1000 - s.created) < 24 * 3600;
    const email = ((s.customer_details && s.customer_details.email) || s.customer_email || '')
      .toString().toLowerCase().trim();

    if (!complete || !recent || !email) { fallback(); return; }

    // Confirm the email currently maps to an active subscription (source of truth),
    // so a refunded/cancelled buyer can't ride an old session id back in.
    const tier = await tierForEmail(email, key);
    if (!tier) { fallback(); return; }

    const session = sign({ e: email, t: tier, x: Date.now() + 30 * 24 * 3600 * 1000 }, process.env.AUTH_SECRET);
    res.setHeader('Set-Cookie', cookie('y3mi', session, 30 * 24 * 3600));
    res.writeHead(302, { Location: '/research/model-adoption/access?tier=' + encodeURIComponent(tier) });
    res.end();
  } catch (e) {
    console.error('auth/checkout', e);
    fallback();
  }
};
