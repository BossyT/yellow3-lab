'use strict';
// Does a claimant already have a live editor link?
//
// This module exists so that the only code writing to public Blob storage on
// the claim path CANNOT SEE AN EMAIL ADDRESS. It is handed an opaque key that
// the caller has already derived, and it stores timestamps and a count. There
// is no parameter here that could carry a person, which is the property the
// build gate is protecting and the reason api/suggest.js leaked a work address
// twice before it existed.
//
// Deliberately not a claims table. The register has no accounts, no moderation
// queue and no claim state: the domain is the join key. This is a short-lived
// record that answers one question - "is a link from an earlier claim still
// valid?" - and nothing else.
//
// Zero-dependency: global fetch, via _lib/blob.

const blob = require('./blob');

const PREFIX = 'dpp/claim-locks/';

// A 64-character hex key, and nothing else, ever. Anything shorter or with a
// slash in it would be a caller passing something it should not.
function pathFor(key) {
  if (!/^[0-9a-f]{64}$/.test(String(key || ''))) throw new Error('claimlock: bad key');
  return PREFIX + key + '.json';
}

// null when there is no live link: the normal case on a first claim, and also
// what a caller gets when the record has aged past its expiry.
async function read(key, now) {
  const rec = await blob.getJson(pathFor(key));
  if (!rec || typeof rec.x !== 'number') return null;
  return rec.x > now ? rec : null;
}

// { i: first issued, x: first expiry, n: how many links sent }. No address, no
// supplier id, no domain - found by URL, this object names nobody.
async function write(key, record) {
  return blob.putJson(pathFor(key), {
    i: record.i, x: record.x, n: record.n,
  });
}

module.exports = { read, write, PREFIX };
