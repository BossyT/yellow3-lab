#!/usr/bin/env python3
"""
OpenRouter pricing + capability layer for the Model Economics pages.

The public /models feed (no auth) gives per-token prices (input / output /
cached), context length, modalities and capabilities; /endpoints gives real
uptime. A daily immutable snapshot under research/model-adoption/_pricing/
accrues price history over time (same pattern as the routing snapshots).

Standard library only, so the daily build stays dependency-free. Prices are
real; latency/throughput are NOT exposed by the API and are never faked.
"""
import os
import json
import glob
import statistics
import urllib.request
import urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
PRICE_DIR = os.path.join(HERE, "model-adoption", "_pricing")
MODELS_URL = "https://openrouter.ai/api/v1/models"
EP_URL = "https://openrouter.ai/api/v1/models/{}/endpoints"


def _get(url, timeout=30):
    req = urllib.request.Request(
        url, headers={"Accept": "application/json", "User-Agent": "yellow3-research/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def fetch_models():
    """Public model feed indexed by canonical_slug and id."""
    data = _get(MODELS_URL).get("data", [])
    by_canon = {m.get("canonical_slug"): m for m in data if m.get("canonical_slug")}
    by_id = {m["id"]: m for m in data}
    return by_canon, by_id, {m["id"] for m in data} | {m.get("canonical_slug") for m in data}


def match(permaslug, by_canon, by_id):
    m = by_canon.get(permaslug) or by_id.get(permaslug)
    if m:
        return m
    base = permaslug.split(":")[0]
    return by_canon.get(base) or by_id.get(base)


def _f(p, k):
    v = p.get(k)
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def extract(m, free_tier):
    p = m.get("pricing", {}) or {}
    a = m.get("architecture", {}) or {}
    sp = set(m.get("supported_parameters", []) or [])
    ins = a.get("input_modalities", []) or []
    return {
        "in": _f(p, "prompt"),
        "out": _f(p, "completion"),
        "cache_read": _f(p, "input_cache_read"),
        "cache_write": _f(p, "input_cache_write"),
        "context": m.get("context_length"),
        "modalities": ins,
        "image_in": "image" in ins,
        "audio_in": "audio" in ins,
        "video_in": "video" in ins,
        "tools": "tools" in sp,
        "structured": "structured_outputs" in sp,
        "reasoning": ("reasoning" in sp) or bool(m.get("reasoning")),
        "open_weight": bool(m.get("hugging_face_id")),
        "free_tier": bool(free_tier),
        "knowledge_cutoff": m.get("knowledge_cutoff"),
        "or_id": m.get("id"),
        "or_url": "https://openrouter.ai/" + (m.get("id") or ""),
    }


def fetch_uptime(model_id, timeout=15):
    """Median 1-day uptime across the model's provider endpoints (real). None on error."""
    try:
        eps = _get(EP_URL.format(model_id), timeout=timeout).get("data", {}).get("endpoints", [])
        ups = [e["uptime_last_1d"] for e in eps if e.get("uptime_last_1d") is not None]
        return round(statistics.median(ups), 3) if ups else None
    except Exception:
        return None


def build_pricing(models_by_slug, with_uptime=True):
    """models_by_slug: {url_slug: model dict from _data/models.json} (each has permaslug).
    Returns {url_slug: economics dict}. Uptime fetched per model (best-effort)."""
    by_canon, by_id, all_ids = fetch_models()
    out = {}
    for slug, mdata in models_by_slug.items():
        perma = mdata.get("permaslug", "")
        m = match(perma, by_canon, by_id)
        if not m:
            continue
        base_id = (m.get("id") or "").split(":")[0]
        free = (base_id + ":free") in all_ids or perma.endswith(":free")
        econ = extract(m, free)
        econ["uptime"] = fetch_uptime(m["id"]) if with_uptime else None
        out[slug] = econ
    return out


# standard workloads for the calculator + price positioning (the same math the
# page's calculator runs client-side; used server-side to rank price position).
WORKLOADS = {
    "coding-agent": {"label": "Coding agent", "tasks": 1000, "inp": 100000, "outp": 10000, "cached": 0.70},
    "customer-support": {"label": "Customer support", "tasks": 50000, "inp": 2000, "outp": 500, "cached": 0.30},
    "document-analysis": {"label": "Document analysis", "tasks": 5000, "inp": 50000, "outp": 2000, "cached": 0.20},
}


def workload_cost(e, w):
    """Monthly USD for economics dict e under workload w. None if no price."""
    if not e or e.get("in") is None or e.get("out") is None:
        return None
    itok = w["tasks"] * w["inp"]
    otok = w["tasks"] * w["outp"]
    crp = e["cache_read"] if e.get("cache_read") is not None else e["in"]
    uncached = itok * (1 - w["cached"]) * e["in"]
    cached = itok * w["cached"] * crp
    out = otok * e["out"]
    return round(uncached + cached + out, 2)


def store_snapshot(pricing, date):
    """One immutable file per date with the price points, for accruing history."""
    os.makedirs(PRICE_DIR, exist_ok=True)
    snap = {slug: {"in": e["in"], "out": e["out"], "cache_read": e["cache_read"]}
            for slug, e in pricing.items()}
    path = os.path.join(PRICE_DIR, date + ".json")
    json.dump({"date": date, "prices": snap}, open(path, "w"), indent=2)
    return path


def load_history():
    """{date: {slug: {in,out,cache_read}}}, oldest first."""
    hist = {}
    for p in sorted(glob.glob(os.path.join(PRICE_DIR, "*.json"))):
        d = json.load(open(p))
        hist[d["date"]] = d["prices"]
    return hist


def price_changes(slug, history):
    """Collapse the daily price series for one model into distinct change points,
    newest first: [{date, in, out, change_pct}]. change_pct is the output-price
    move vs the prior distinct point (the headline figure)."""
    pts = []
    for date in sorted(history):
        pr = history[date].get(slug)
        if not pr or pr.get("out") is None:
            continue
        if not pts or pts[-1]["out"] != pr["out"] or pts[-1]["in"] != pr["in"]:
            pts.append({"date": date, "in": pr["in"], "out": pr["out"]})
    rows = []
    for i, p in enumerate(pts):
        prev = pts[i - 1] if i > 0 else None
        chg = None
        if prev and prev["out"]:
            chg = round(100 * (p["out"] - prev["out"]) / prev["out"], 1)
        rows.append({"date": p["date"], "in": p["in"], "out": p["out"], "change_pct": chg})
    rows.reverse()
    return rows
