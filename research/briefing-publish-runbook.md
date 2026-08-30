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

**Per language.** Since GPT's ruling of 30 August 2026 an edition is identified
by locale *plus* date, so an English and a Spanish edition of one Monday are two
separate editions with two of everything below.

| What | Where it goes | Notes |
|---|---|---|
| The recording | `media/briefing/<presenter>-YYYY-MM-DD-<locale>.mp4` | run it through `research/briefing_media.py` — it re-encodes, **refuses a landscape or square file**, and **refuses** if the audio is not bit-for-bit identical |
| The poster | `media/briefing/<presenter>-YYYY-MM-DD-<locale>.jpg` | a frame from *this* recording |
| Measured duration | `video.durationSeconds` | read from the file, never typed |
| Measured shape | `video.width`, `video.height` | printed by `briefing_media.py`. Must be portrait; the deploy gate refuses otherwise |
| Locale | `locale` | `en` or `es`. Absent means English |
| Four timing markers | `stories[].startSeconds` | measured, then **listened to** |
| Sources | `sources[]` | each needs publisher, title, https url, `checkedAt` |
| Transcript | `transcript[]` | full |

`briefing_media.py` prints the whole `video` block ready to paste, with the
duration and the shape already measured. Type none of those three by hand.

---

## The sequence

```bash
# 0. prepare each recording. Once per language. Refuses a landscape file.
python3 research/briefing_media.py "<source.mp4>" YYYY-MM-DD en
python3 research/briefing_media.py "<source.mp4>" YYYY-MM-DD es
#    then copy the two files it names into media/briefing/ and paste the
#    printed video block into research/briefings.json

# 1. validate before anything is written
python3 research/gen_briefing.py --check

# 2. write the pages. English to /research/..., Spanish to /es/research/...
python3 research/gen_briefing.py

# 3. render the social cards. OG_BUILD_DIR MUST BE OUTSIDE THE REPO — see below.
export OG_BUILD_DIR="$HOME/.cache/yellow3-og"
python3 research/gen_og.py

# 4. THE STEP THAT IS EASY TO MISS — see below. One card per language.
cp "$OG_BUILD_DIR/out/research-digital-product-passport-weekly-briefing-YYYY-MM-DD.png" og/cards/
cp "$OG_BUILD_DIR/out/es-research-digital-product-passport-weekly-briefing-YYYY-MM-DD.png" og/cards/

# 5. the gate. This IS the Vercel build command.
python3 research/build_check.py

# 6. ship
git add -A && python3 research/build_check.py && git commit && git push
```

**`git add -A` is load-bearing, and this is not a style note.** The 307 that
makes `/research/digital-product-passport/weekly-briefing` resolve is written by
the generator into `vercel.json`. When edition 001 shipped, that change was left
behind, and the permanent route returned **404 in production from launch until
30 August 2026** while every dated URL worked perfectly. Nothing detects it: the
gate does not fetch the site, and the route that is broken is the one nobody on
the team uses, because they all have the dated link. Check `git status` for
`vercel.json` before you commit.

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

**Set it OUTSIDE the repo.** On 30 August it was pointed at `./scratchpad/og-002`,
which is git-ignored and therefore looked harmless. It is not: the build directory
holds ~32 staging HTML pages, and `build_check` globs the working tree rather than
the commit, so the page count jumped from 653 to 687 and the gate was counting
files that will never deploy. Nothing failed, which is the problem — the numbers the
gate reports are the ones you would use to spot a real change. `$HOME/.cache` or
`/tmp` keeps it out of the tree.

**There is no `-index` card any more.** The old step 4 copied
`...-weekly-briefing-index.png` alongside the dated card. Since the permanent route
became a 307 it serves no HTML, so `gen_og.py` never renders that card and the `cp`
fails with *No such file or directory* — in the middle of a run whose last line still
says `build checks passed`, because nothing references the card either. Harmless, and
exactly the kind of failure that gets copied forward for months.

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

## The shape gate, added 30 August 2026

A landscape 1280x720 recording was delivered for edition 002 and **nothing in
the pipeline would have stopped it.** `briefing_media.py` checked duration,
resolution stability and audio identity — every question about whether a file
had been degraded, and none about whether it was the right shape. `build_check`
had never looked at the video at all.

The stage is portrait at every breakpoint — 400x510, 330x470, and full width by
`min(124vw, 570px)` — with `object-fit: contain` part of the design lock. A 16:9
file renders as a band across the middle with 55–60% of the stage empty, and the
topline and play control, pinned to the stage edges, sit over background instead
of over the presenter. No encode setting fixes it. It is the wrong shape.

It is now refused in three places: at the source by `briefing_media.py`, in the
edition data by `gen_briefing.py --check`, and at deploy by `build_check.py`.
The deploy gate reads `video.width` and `video.height` from `briefings.json`
rather than probing the file, because Vercel builds this repo with python and no
ffmpeg — a gate that needs a binary the builder does not have is a gate that
gets deleted the first morning it blocks a deploy.

## Two languages

GPT's ruling of 30 August 2026 settled the IA this runbook previously left open.

- The unprefixed route is **always English**; `/es/` is **always Spanish**.
- Edition identity is locale plus date. Media filenames, social cards and the
  newest-edition resolution all carry the locale.
- Each dated page is a separate indexable document and is self-canonical.
- Each language's permanent route is a **307 to its own newest dated edition**.
  Neither serves HTML, so the latest/archive duplication is gone.
- Matching dated editions carry reciprocal `hreflang` links, with the English
  dated edition as `x-default`. A page with no translation gets no alternates at
  all — a self-referential hreflang on a document with no counterpart tells a
  crawler a translation exists.
- **No** redirect by browser language, and **no** language selector inside the
  frozen frame.

The listing entry points — `research.html` and the instrument page — are English
pages and follow the English series only. Nothing points a reader at `/es/`
except an hreflang alternate or a deliberate Spanish link.

### What is still English on a Spanish page

Dates are derived and render in Spanish. **Authored copy is not translated**,
because inventing it is design work, not integration. Twenty-nine strings the
generator and the shared site shell emit still render in English on an `/es/`
page — the breadcrumb `Weekly Briefing`, the section labels `Sources`,
`Transcript`, `Video position`, `WEEK COVERED`, `Latest edition`, `Earliest
edition`, the control labels `PLAY`, `PLAY WITH SOUND`, `SOUND ON`, the two
state lines `Evidence checked before publication.` / `PENDING`, the standing
line `What changed this week.`, the four category tags `REGULATORY`,
`DEADLINES`, `IMPLEMENTATION`, `STANDARDS`, and the nav and footer inherited
from `research.html`. They need GPT's translations before a Spanish edition is
fit to publish.
