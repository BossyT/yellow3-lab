'use strict';
// Does the claim flow behave the way api/claim.js says it does?
//
// The spec, in its own words: "The whole check is: does the sender's email
// domain match the domain that defines this row? The register's join key IS the
// domain, so a work email at that domain proves the person belongs to the
// company. No accounts, no moderation queue... Nobody at yellow3 is in the loop:
// the supplier writes their own layer themselves."
//
// Nothing here writes anything and no mail can leave: global fetch is replaced
// before the handler is loaded, so every send is captured instead of sent.
//
//   node research/dpp_claim_spec_test.js

const fs = require('fs');
const path = require('path');

process.chdir(path.join(__dirname, '..'));

// Capture every outbound send. If a test ever hits the real Resend API this
// throws instead, which is the point.
const sent = [];
global.fetch = async (url, opts) => {
  if (String(url).includes('api.resend.com')) {
    sent.push(JSON.parse(opts.body));
    return { ok: true, status: 200, text: async () => 'ok' };
  }
  throw new Error('unexpected network call to ' + url);
};

process.env.RESEND_API_KEY = 'test-key';
process.env.FROM_EMAIL = 'yellow3 Model Intelligence <access@yellow3.io>';
process.env.CLAIM_NOTIFY_EMAIL = 'register@yellow3.io';
process.env.AUTH_SECRET = 'test-secret-for-spec-tests';
delete process.env.CLAIM_TEST_DOMAIN;

const claim = require('../api/claim.js');
const { verify } = require('../api/_lib/util.js');

const rows = JSON.parse(
  fs.readFileSync(path.join(process.cwd(), 'research', 'dpp-suppliers.json'), 'utf8')
).suppliers;
const withDomain = rows.find(r => r.domain && r.id);

let pass = 0, fail = 0;
const logs = [];
const realLog = console.log, realErr = console.error;
function capture(on) {
  if (on) {
    console.log = (...a) => logs.push(String(a[0]));
    console.error = (...a) => logs.push(String(a[0]));
  } else {
    console.log = realLog; console.error = realErr;
  }
}

async function call(method, body) {
  sent.length = 0; logs.length = 0;
  let status = 0, payload = null, headers = {};
  const res = {
    setHeader: (k, v) => { headers[k] = v; },
    status(c) { status = c; return this; },
    json(o) { payload = o; return this; },
  };
  capture(true);
  try {
    await claim({ method, body }, res);
  } finally {
    capture(false);
  }
  const outcomes = logs.map(l => { try { return JSON.parse(l).outcome; } catch (e) { return null; } });
  return { status, payload, headers, sent: sent.slice(), outcomes };
}

function check(name, cond, detail) {
  if (cond) { pass++; console.log('  ok    ' + name); }
  else { fail++; console.log('  FAIL  ' + name + (detail ? '  -> ' + detail : '')); }
}

(async () => {
  console.log('\nCLAIM FLOW, against the contract in api/claim.js\n');

  let r = await call('GET', {});
  check('GET is refused with 405 and an Allow header',
        r.status === 405 && r.headers.Allow === 'POST', 'status ' + r.status);

  r = await call('POST', { email: 'someone@gmail.com', supplier: withDomain.id });
  check('a public mailbox never receives a claim link',
        r.outcomes.includes('public_mailbox') && r.sent.length === 0,
        r.outcomes.join(','));

  r = await call('POST', { email: 'a@example.com', supplier: 'no-such-supplier-xyz' });
  check('an unknown supplier id sends nothing',
        r.outcomes.includes('unknown_supplier') && r.sent.length === 0,
        r.outcomes.join(','));

  r = await call('POST', { email: 'someone@definitely-not-this-company.example',
                           supplier: withDomain.id });
  const nearMiss = r.sent.filter(m => /no domain match/i.test(m.subject));
  check('a non-matching domain gets no link, and we are told it happened',
        r.outcomes.includes('no_domain_match') && nearMiss.length === 1
        && !r.sent.some(m => m.to[0] !== process.env.CLAIM_NOTIFY_EMAIL),
        'outcomes ' + r.outcomes.join(',') + ' sent ' + r.sent.length);

  r = await call('POST', { email: 'anna@' + withDomain.domain, supplier: withDomain.id });
  const toClaimant = r.sent.filter(m => m.to[0] === 'anna@' + withDomain.domain);
  check('a matching work email is verified and receives a link',
        r.outcomes.includes('verified') && toClaimant.length === 1,
        'outcomes ' + r.outcomes.join(','));

  const link = (toClaimant[0] && /\/api\/claim-verify\?t=([^"&]+)/.exec(toClaimant[0].html)) || null;
  check('the link carries a signed token this deployment can verify',
        !!link && !!verify(decodeURIComponent(link[1]), process.env.AUTH_SECRET));

  if (link) {
    const tok = verify(decodeURIComponent(link[1]), process.env.AUTH_SECRET);
    const hours = (tok.x - Date.now()) / 3600000;
    check('the link expires in 24 hours, as LINK_TTL_MS says',
          hours > 23.5 && hours < 24.5, hours.toFixed(2) + 'h');
    check('the token is bound to that supplier row and that email',
          tok.sid === withDomain.id && tok.email === 'anna@' + withDomain.domain);
  }

  const aliased = rows.find(r2 => String(r2.alias_domains || '').trim());
  if (aliased) {
    const alias = String(aliased.alias_domains).split(',')[0].trim();
    r = await call('POST', { email: 'anna@' + alias, supplier: aliased.id });
    check('an alias domain reaches the right profile',
          r.outcomes.includes('verified'), r.outcomes.join(','));
  } else {
    console.log('  ..    no alias_domains in the register to exercise');
  }

  const shapes = await Promise.all([
    call('POST', { email: 'someone@gmail.com', supplier: withDomain.id }),
    call('POST', { email: 'a@example.com', supplier: 'no-such-supplier-xyz' }),
    call('POST', { email: 'anna@' + withDomain.domain, supplier: withDomain.id }),
  ]);
  check('every answer is identical, so the form cannot enumerate who works where',
        shapes.every(s => s.status === 200 && JSON.stringify(s.payload) === '{"ok":true}'));

  console.log('\n  ' + pass + ' passed, ' + fail + ' failed\n');
  process.exit(fail ? 1 : 0);
})();
