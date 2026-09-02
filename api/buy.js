'use strict';
// GET /api/buy?offer=<slug>  ->  303 to a Stripe Checkout Session, priced in EUR.
//
// WHY THIS EXISTS. The five advisory offers were sold through Stripe Payment
// Links. Payment Links force Adaptive Pricing on - Stripe's own words are
// "Adaptive Pricing is always enabled for Payment Links" - so a buyer outside
// the eurozone was shown their local currency first, with a 2-4% conversion fee
// folded into the rate. Thomas ruled on 2 September 2026: EUR only.
//
// Adaptive Pricing CAN be switched off on a Checkout Session, which a Payment
// Link cannot do at any price. So the buttons point here instead, and this
// creates the session with adaptive_pricing[enabled]=false.
//
// THE PAYMENT LINKS REMAIN THE SOURCE OF TRUTH. This does not hardcode price
// ids. It reads the price off the payment link that already sells the offer, so
// changing a price in Stripe changes what this charges, and there is no second
// place to keep in step. The lookup is cached per instance.
//
// NEVER A DEAD BUY BUTTON. If Stripe is unreachable, the key is missing, or the
// offer cannot be resolved, this redirects to the payment link itself. The
// buyer then sees the old currency behaviour, which is worse than EUR and far
// better than a broken checkout.
//
// Zero-dependency: Node built-ins + global fetch, same as the rest of /api.

const SITE = 'https://www.yellow3.io';

// slug -> the live payment link that already sells this offer.
// Verified in a real browser on 2 September 2026: correct product, correct EUR
// price, collecting full name, business name and email.
const OFFERS = {
  'market-readiness':    '7sY3cxa2m0K892G8fOawo09',  // EUR 4,900
  'advisory-session':    'dRm00l6Qa3WkbaO8fOawo00',  // EUR   490
  'executive-briefing':  'bJe3cx0rM1OcdiWanWawo02',  // EUR 1,500
  'board-briefing':      '28E28t1vQfF21Ae67Gawo03',  // EUR 3,000
  'leadership-workshop': '8x2cN75M6eAYgv88fOawo04',  // EUR 4,500
};

const PRICE_CACHE = new Map();

function form(obj) {
  return Object.keys(obj)
    .map((k) => encodeURIComponent(k) + '=' + encodeURIComponent(obj[k]))
    .join('&');
}

async function stripe(path, key, body) {
  const init = { headers: { Authorization: 'Bearer ' + key } };
  if (body) {
    init.method = 'POST';
    init.headers['content-type'] = 'application/x-www-form-urlencoded';
    init.body = form(body);
  }
  const res = await fetch('https://api.stripe.com/v1/' + path, init);
  if (!res.ok) throw new Error('stripe ' + res.status + ' ' + (await res.text()));
  return res.json();
}

// The payment link's own line item tells us the price. One call, then cached.
async function priceFor(linkId, key) {
  if (PRICE_CACHE.has(linkId)) return PRICE_CACHE.get(linkId);
  const items = await stripe(
    'payment_links/' + encodeURIComponent(linkId) + '/line_items?limit=1', key);
  const price = items && items.data && items.data[0] && items.data[0].price
    && items.data[0].price.id;
  if (!price) throw new Error('no price on payment link ' + linkId);
  PRICE_CACHE.set(linkId, price);
  return price;
}

module.exports = async (req, res) => {
  res.setHeader('Cache-Control', 'no-store');

  const offer = ((req.query && req.query.offer) || '').toString();
  const linkId = Object.prototype.hasOwnProperty.call(OFFERS, offer)
    ? OFFERS[offer] : null;

  // An unknown offer is a link somebody typed or a button that got renamed.
  // Send them to the page that lists all five rather than to a Stripe error.
  if (!linkId) {
    res.writeHead(303, { Location: SITE + '/advisory' });
    res.end();
    return;
  }

  const paymentLink = 'https://buy.stripe.com/' + linkId;
  const degrade = function (why, err) {
    console.error('buy: falling back to the payment link', offer, why, err || '');
    res.writeHead(303, { Location: paymentLink });
    res.end();
  };

  const key = process.env.STRIPE_SECRET_KEY;
  if (!key) { degrade('no STRIPE_SECRET_KEY'); return; }

  try {
    const price = await priceFor(linkId, key);
    const session = await stripe('checkout/sessions', key, {
      mode: 'payment',
      'line_items[0][price]': price,
      'line_items[0][quantity]': '1',
      // The whole reason this endpoint exists.
      'adaptive_pricing[enabled]': 'false',
      // Match what the payment links collect: full name, business name, email.
      // Email is always collected by Checkout.
      'name_collection[individual][enabled]': 'true',
      'name_collection[business][enabled]': 'true',
      // {CHECKOUT_SESSION_ID} is Stripe's own placeholder: it substitutes the
      // real id on redirect, so the confirmation page can verify the purchase
      // server-side instead of trusting anything in the URL.
      success_url: SITE + '/advisory/confirmation?session_id={CHECKOUT_SESSION_ID}',
      cancel_url: SITE + '/advisory',
      'metadata[offer]': offer,
      'metadata[source]': 'advisory',
    });
    if (!session || !session.url) { degrade('session had no url'); return; }
    res.writeHead(303, { Location: session.url });
    res.end();
  } catch (e) {
    degrade('stripe call failed', e && e.message);
  }
};
