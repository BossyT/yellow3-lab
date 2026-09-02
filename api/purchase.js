'use strict';
// GET /api/purchase?session_id=cs_...  ->  { paid, offer, offer_name, amount, email, business }
//
// The confirmation page at /advisory/confirmation renders nothing until this
// answers. Ruled by GPT on 2 September 2026:
//
//   - derive the offer, amount and customer details from the server-verified
//     Checkout Session, never from editable URL text
//   - show "Payment confirmed" only after Stripe reports the session as paid
//   - display amounts as "EUR 4,900" - never a converted currency, and never
//     the euro symbol alone
//
// So this returns paid:false unless Stripe itself says the session is paid, and
// it formats the amount from the session's OWN currency and total. A session id
// is not a secret worth much - it is single-use, expires, and reveals only what
// the buyer just bought - but nothing here is taken on the caller's word.
//
// Zero-dependency: Node built-ins + global fetch, same as the rest of /api.

const OFFER_NAME = {
  'market-readiness': 'Digital Product Passport Market Readiness',
  'advisory-session': 'Advisory Session',
  'executive-briefing': 'Executive Briefing',
  'board-briefing': 'Board Briefing',
  'leadership-workshop': 'Leadership Workshop',
};

// "EUR 4,900". Stripe reports minor units; EUR advisory prices are whole euros,
// so cents are shown only if a price ever has them.
function money(amountMinor, currency) {
  if (typeof amountMinor !== 'number' || !currency) return null;
  const code = String(currency).toUpperCase();
  const major = amountMinor / 100;
  const whole = Math.floor(major);
  const cents = Math.round((major - whole) * 100);
  const grouped = String(whole).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  return code + ' ' + grouped + (cents ? '.' + String(cents).padStart(2, '0') : '');
}

async function stripeGet(path, key) {
  const res = await fetch('https://api.stripe.com/v1/' + path, {
    headers: { Authorization: 'Bearer ' + key },
  });
  if (!res.ok) throw new Error('stripe ' + res.status + ' ' + (await res.text()));
  return res.json();
}

module.exports = async (req, res) => {
  res.setHeader('Cache-Control', 'no-store');
  res.setHeader('content-type', 'application/json');

  const sid = ((req.query && req.query.session_id) || '').toString();
  const no = function (reason) {
    // Never 500 at the buyer. The page has a truthful unconfirmed state and
    // shows it; an error status would only turn that into a browser error.
    res.statusCode = 200;
    res.end(JSON.stringify({ paid: false, reason: reason }));
  };

  if (!/^cs_[A-Za-z0-9_]+$/.test(sid)) { no('bad_session_id'); return; }

  const key = process.env.STRIPE_SECRET_KEY;
  if (!key) { no('no_key'); return; }

  try {
    const s = await stripeGet('checkout/sessions/' + encodeURIComponent(sid), key);

    // Stripe's word, not the caller's.
    const paid = s.status === 'complete' &&
      (s.payment_status === 'paid' || s.payment_status === 'no_payment_required');
    if (!paid) { no('not_paid'); return; }

    const offer = (s.metadata && s.metadata.offer) || '';
    const details = s.customer_details || {};

    res.statusCode = 200;
    res.end(JSON.stringify({
      paid: true,
      offer: Object.prototype.hasOwnProperty.call(OFFER_NAME, offer) ? offer : null,
      offer_name: OFFER_NAME[offer] || null,
      // amount_total is in the session's own currency, which is EUR because
      // /api/buy creates the session with adaptive_pricing disabled.
      amount: money(s.amount_total, s.currency),
      email: details.email || s.customer_email || null,
      business: details.business_name || null,
    }));
  } catch (e) {
    console.error('purchase', e && e.message);
    no('lookup_failed');
  }
};
