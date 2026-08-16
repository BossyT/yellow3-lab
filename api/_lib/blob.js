'use strict';
// Vercel Blob, hand-rolled. The register's static pages are built and committed;
// anything a company supplies about itself arrives at runtime, when the repo is
// read-only, so it lives here instead.
//
// Deterministic pathnames (no random suffix) so a supplier's record is always at
// the same place and can be overwritten when they edit it again.
// Zero-dependency: global fetch only.

const API = 'https://blob.vercel-storage.com';

// A SEPARATE, PUBLIC store. BLOB_READ_WRITE_TOKEN points at the private store
// holding the paid report PDF, which rejects public writes outright - and it
// should: a paid report and a company's logo are not the same kind of content
// and do not belong in one bucket. Supplied content is public by definition.
function token() {
  const t = process.env.BLOB_PUBLIC_RW_TOKEN || process.env.BLOB_READ_WRITE_TOKEN;
  if (!t) throw new Error('BLOB_PUBLIC_RW_TOKEN missing');
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
async function put(pathname, body, contentType, maxAgeSec) {
  const res = await fetch(API + '/' + String(pathname).replace(/^\/+/, ''), {
    method: 'PUT',
    headers: {
      authorization: 'Bearer ' + token(),
      'x-api-version': '7',
      'x-content-type': contentType || 'application/octet-stream',
      'x-add-random-suffix': '0',
      'x-cache-control-max-age': String(maxAgeSec == null ? 60 : maxAgeSec),
    },
    body: body,
  });
  if (!res.ok) throw new Error('blob put ' + res.status + ' ' + (await res.text()));
  return res.json();
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

// List by prefix. Used to see how many submissions are waiting without
// reading who they are - the intake runbook keeps unrecorded companies private,
// so the queue is counted, never published.
async function list(prefix, limit) {
  const url = API + '?prefix=' + encodeURIComponent(prefix) +
              '&limit=' + String(limit || 1000);
  const res = await fetch(url, {
    headers: { authorization: 'Bearer ' + token(), 'x-api-version': '7' },
    cache: 'no-store',
  });
  if (!res.ok) throw new Error('blob list ' + res.status);
  const body = await res.json();
  return Array.isArray(body.blobs) ? body.blobs : [];
}

module.exports = { put, putJson, getJson, getRaw, publicUrl, list };
