'use strict';
// Vercel Blob, hand-rolled. The register's static pages are built and committed;
// anything a company supplies about itself arrives at runtime, when the repo is
// read-only, so it lives here instead.
//
// Deterministic pathnames (no random suffix) so a supplier's record is always at
// the same place and can be overwritten when they edit it again.
// Zero-dependency: global fetch only.

const API = 'https://blob.vercel-storage.com';

function token() {
  const t = process.env.BLOB_READ_WRITE_TOKEN;
  if (!t) throw new Error('BLOB_READ_WRITE_TOKEN missing');
  return t;
}

// vercel_blob_rw_<storeId>_<secret> -> the store's public read host.
function publicBase() {
  const parts = String(token()).split('_');
  if (parts.length < 4) throw new Error('BLOB token malformed');
  return 'https://' + parts[3] + '.public.blob.vercel-storage.com/';
}

function publicUrl(pathname) {
  return publicBase() + String(pathname).replace(/^\/+/, '');
}

// The store is PRIVATE - it was created to hold the gated report PDF. Writes
// must declare private access or the API rejects them, and every read has to
// carry the token. Nothing here is reachable by URL alone, which is why the
// logo is served through /api/logo rather than linked directly.
// The store rejects anything it reads as a public write, and the header that
// declares otherwise is not documented for the raw API. Rather than burn a
// round trip per guess, try the plausible spellings in one call and log which
// one the store accepts, so this can collapse to that single variant.
const ACCESS_VARIANTS = [
  { v: '11', h: { 'x-access': 'private' } },
  { v: '7', h: { 'x-blob-access': 'private' } },
  { v: '11', h: { 'x-access-level': 'private' } },
  { v: '11', h: {} },
  { v: '7', h: {} },
];

async function put(pathname, body, contentType, maxAgeSec) {
  const clean = String(pathname).replace(/^\/+/, '');
  const tried = [];
  for (const variant of ACCESS_VARIANTS) {
    const headers = Object.assign({
      authorization: 'Bearer ' + token(),
      'x-api-version': variant.v,
      'x-content-type': contentType || 'application/octet-stream',
      'x-add-random-suffix': '0',
      'x-cache-control-max-age': String(maxAgeSec == null ? 60 : maxAgeSec),
    }, variant.h);

    const res = await fetch(API + '/' + clean, { method: 'PUT', headers, body });
    if (res.ok) {
      console.log(JSON.stringify({
        evt: 'blob_put', outcome: 'ok', pathname: clean,
        accepted: { api_version: variant.v, headers: Object.keys(variant.h) },
      }));
      return res.json();
    }
    const text = await res.text();
    tried.push(variant.v + '+' + (Object.keys(variant.h)[0] || 'none') + ' -> ' + res.status + ' ' + text.slice(0, 140));
  }
  throw new Error('blob put failed; tried: ' + tried.join(' | '));
}

async function getRaw(pathname) {
  let url;
  try { url = publicUrl(pathname); } catch (e) { return null; }
  const res = await fetch(url + '?t=' + Date.now(), {
    headers: { authorization: 'Bearer ' + token() },
    cache: 'no-store',
  });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error('blob get ' + res.status);
  return res;
}

// null when nothing has been stored yet - an unclaimed supplier is the normal
// case, not an error.
async function getJson(pathname) {
  const res = await getRaw(pathname);
  if (!res) return null;
  try { return await res.json(); } catch (e) { return null; }
}

async function putJson(pathname, obj) {
  return put(pathname, JSON.stringify(obj), 'application/json', 0);
}

module.exports = { put, putJson, getJson, getRaw, publicUrl };
