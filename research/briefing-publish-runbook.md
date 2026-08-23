# Publishing a Monday Briefing edition

Written 23 August 2026 after a full dry run of edition 002 against the real
generators. Every step below was executed and every failure named here actually
happened — this is not a checklist somebody imagined.

The design is frozen. This runbook is about getting a new edition *through the
machinery*, not about changing anything.

---

## Before the morning

Have these ready. The gate refuses the edition without them, and three of them
cannot be produced in a hurry:

| What | Where it goes | Notes |
|---|---|---|
| The recording | `media/briefing/astrid-YYYY-MM-DD.mp4` | run it through `research/briefing_media.py` — it re-encodes and **refuses** if Astrid's audio is not bit-for-bit identical |
| The poster | `media/briefing/astrid-YYYY-MM-DD.jpg` | a frame from *this* recording |
| Measured duration | `video.durationSeconds` | read from the file, never typed |
| Four timing markers | `stories[].startSeconds` | measured, then **listened to** |
| Sources | `sources[]` | each needs publisher, title, https url, `checkedAt` |
| Transcript | `transcript[]` | full |

---

## The sequence

```bash
# 1. validate before anything is written
python3 research/gen_briefing.py --check

# 2. write the pages
python3 research/gen_briefing.py

# 3. render the social cards
python3 research/gen_og.py

# 4. THE STEP THAT IS EASY TO MISS — see below
cp "$OG_BUILD_DIR/out/research-digital-product-passport-weekly-briefing-YYYY-MM-DD.png" og/cards/
cp "$OG_BUILD_DIR/out/research-digital-product-passport-weekly-briefing-index.png" og/cards/

# 5. the gate. This IS the Vercel build command.
python3 research/build_check.py

# 6. ship
git add -A && python3 research/build_check.py && git commit && git push
```

---

## The one that will bite you

**`gen_og.py` does not write into `og/cards/`.** It renders into a build
directory and stops, deliberately — the docstring says wiring is a separate step
taken only after the contact sheet is reviewed.

So on publication morning the sequence goes: the build gate refuses with

```
1 page(s) point at a social card that does not exist, e.g.
research/.../weekly-briefing/2026-08-31.html -> cards/...-2026-08-31.png
  - run research/gen_og.py
```

you run `gen_og.py` exactly as instructed, it reports `rendered 299/299` with no
error, **and the gate still refuses**, because the card is sitting in the build
directory. The advice in that message is incomplete. The missing move is step 4:
copy the new card, and the refreshed `-index` card, into `og/cards/`.

`OG_BUILD_DIR` defaults to a session scratchpad path from August 2026 that no
longer exists; `gen_og.py` recreates it, so the cards do get written — just
somewhere you would not think to look. **Set `OG_BUILD_DIR` yourself** so you
know where they landed.

A failing gate is not a warning. Vercel keeps serving the previous build and the
site looks fine from outside. That is how three days of stale deploys happened
in August.

---

## What the gate refuses, and why each one exists

`gen_briefing.py --check` blocks on all of these. None can be waved through:

- no issue number or research note, or the literal `TBC`
- `checkedAt` unset, without an offset, **in the future**, or earlier than one of
  its own sources — an instrument whose claim is that evidence was checked
  cannot date that check tomorrow
- the handover's sample duration (53.527s) or sample markers `[0, 14, 27, 41]`,
  which belong to a different script
- fewer or more than four stories; non-numeric markers; markers out of order;
  story 01 not starting at 0; the last marker beyond the duration
- `markersConfirmed` false — somebody has to **listen**. Measured is not
  approved.
- an empty transcript, an empty source list, or a source missing any of
  publisher / title / url / checkedAt, or a url that is not `https://`
- the standalone abbreviation `DPP` in any story headline or consequence

### Two traps in the data itself

**Do not copy edition 001's JSON as a template without pruning it.** It carries
`publishApproval`, a one-off GPT authorisation from 23 August that releases the
two human gates — `markersConfirmed` and `checkedAt`. Inherited silently, it
lets an edition publish with unconfirmed markers and no evidence timestamp. A
normal edition should have neither the approval nor a reason for it. Also drop
`markersNote`, `checkedAtNote` and `surfaceRuling`, which are all issue-001
history.

**`video.presenter` is required and used to be checked nowhere.** An edition
whose video block was rebuilt by hand without it passed `--check` as
*publishable* and then died with a `KeyError` mid-render. That gap was found on
this dry run and closed; the gate now names it. Mentioned because it is the
shape of fault to expect from hand-edited JSON — a field the renderer needs and
the gate never asked for.

---

## What happens automatically, and needs no work

Verified on the dry run with two editions present:

- **The archive navigation links itself up.** The permanent route gains
  `← 17-23 AUGUST 2026` pointing at edition 001; 001 gains a forward link to
  002. The 2026-08-24 page stops being an orphan the moment 002 publishes, with
  no intervention.
- **The sitemap picks the new page up** on the next build, at its canonical URL.
- **`og:image` tags are already correct** — `gen_briefing.py` derives the card
  name from the page path, so `wire_og.py` is not needed for these pages. Only
  the file copy is.

---

## Still open, for GPT rather than for this runbook

The permanent route and the newest dated edition are byte-identical content at
two indexable URLs, each self-canonical. Today that is one week of duplication;
from edition 002 it is permanent. It needs an IA decision — a canonical policy,
or an archive index — and it is not a thing to settle on a Monday morning.
