# yellow3 Insights RSS and subscription experience — v1.1 decision record

Date: 23 August 2026
Design owner: ChatGPT
Approved by: Thomas Christian Melskens
Status: RATIFIED, implemented and deployed

This record **supersedes one boundary** in the approved v1.0 handover and
ratifies the implementation decisions taken against it. **v1.0 is not
rewritten.** Everything in v1.0 that is not named below still stands exactly as
approved, including every lock.

---

## 1. The feed-view visual boundary is superseded

**v1.0, `03-RSS-BROWSER-SPEC.md`, "Visual boundary":**

> The browser presentation has no yellow3 top menu, no footer, no logo and no
> substitute navigation. It is a machine endpoint with a restrained
> human-readable layer.

**v1.1 supersedes that paragraph, and only that paragraph, and only for the
browser presentation of `/feed.xml`.** The existing yellow3 top menu and footer
are carried on that page as they are on every other page of the site.

Nothing else in `03-RSS-BROWSER-SPEC.md` changes. In particular the core
requirement is untouched: `/feed.xml` remains a valid RSS 2.0 document, the
presentation is a layer applied to that XML, feed readers never receive HTML,
and there is no production `/feed-preview` route.

### Conditions attached to the override

All four are implemented and asserted, not left to a reading:

1. The existing shell retains its existing tokens.
2. The feed presentation remains scoped beneath `.fv1`.
3. Signal yellow remains `#FFE500`.
4. No package token may repaint the existing menu or footer.

The site shell and the approved package disagree about four tokens, which is
why condition 4 needs machinery rather than good intentions:

| Token | Site shell | Approved package |
|---|---|---|
| `--ink` | `#0e0e0e` | `#171717` |
| `--line` | `#e7e6e2` | `#d5d7d7` |
| `--muted` | `#8a8a8a` | `#6b6b6b` |
| `--yellow` | `#ffe000` | `#ffe500` |

The nav and footer read `--ink`, `--line` and `--yellow` twenty-one times
between them. The shell stays at document level; the package is scoped beneath
`.fv1` by `research/port_approved_css.py`'s own transform, imported rather than
reimplemented, with the declaration count asserted.

### The two obsolete acceptance checks are replaced

`08-ACCEPTANCE-CHECKS.md` carried two checks that passed by absence:

> - [ ] The RSS browser presentation does not render a top menu.
> - [ ] The RSS browser presentation does not render a footer.

Those two are **retired**. They are replaced by:

- [x] The RSS browser presentation renders exactly one existing yellow3 top
      menu and one existing yellow3 footer.
- [x] No substitute shell, duplicated shell or altered shell styling is
      present.

Both replacements are enforced by `research/build_check.py`, which is the
Vercel build command — see `2b3` in that file. The check proves the menu and
footer markup on `/feed.xml` are byte-identical to the ones the rest of the
site carries, so "existing" is a measured property rather than a claim.

---

## 2. The opening beneath the fixed menu

The signal rule must not touch the menu border. The feed view opens with the
subscription page's rhythm:

- **38px** of clear space beneath the menu at desktop and tablet.
- **26px** of clear space beneath the mobile menu.
- The 7px signal rule follows that space.
- All internal feed-view geometry beneath the rule is preserved.

The nav is `position: fixed`, 74.6px tall above 880px and 67px below it. The
clear space is **added** to the nav height, never substituted for it, in three
bands, because the nav changes height at 880px while the clear space changes at
560px:

| Viewport | Nav | Clear space | `padding-top` |
|---|---|---|---|
| above 880px | 74.6px | 38px | `calc(74.6px + 38px)` |
| 561–880px | 67px | 38px | `calc(67px + 38px)` |
| 320–560px | 67px | 26px | `calc(67px + 26px)` |

Applied to `.feed-view`, not `.feed-view-intro`: the rule is absolutely
positioned at the intro's top, so padding the intro would leave the rule behind
the menu rather than below it.

---

## 3. Ratified deviations

All four production deviations on `/insights/subscribe` are ratified as
implementation necessities that preserve the approved visual and accessibility
requirements. Each stays attributed in `research/port_approved_css.py`, emitted
after the mechanical port and never folded into it.

1. **Nav clearance** — the approved 38px opening added to the fixed nav's
   height rather than replacing it.
2. **No underline on linked latest-entry titles** — the package's rows are
   placeholders and carry no anchors, so it has no rule for one.
3. **No underline on linked feed-entry titles and arrows** — same cause, on
   the feed view, where every row is required to link.
4. **The visually hidden live region** for copy confirmation — required in
   prose by `04-INTERACTIONS-AND-STATES.md`, which the package has no rule for.

---

## 4. Issue 31 carries its full name

The published visible title becomes:

> The Digital Product Passport Deadline You Already Missed

Propagated from the article source record to the article, the RSS item, the
subscription page, page metadata, social metadata and internal listings.

**The existing slug and canonical URL are unchanged**
(`/insights/the-dpp-deadline-you-already-missed`). No redirect was created and
the article URL did not move.

The inherited footer label `DPP Supplier Register` is outside this build and
remains untouched. The acceptance rule that applies to this build is that **no
standalone abbreviation appears in the content area, article titles or newly
generated metadata** — which is narrower than, and replaces, the earlier
reporting that Issue 31 was the only public occurrence.

---

## 5. Ratified implementation decisions

- Latest entries are read from the existing feed at build time.
- Issue labels are read from article metadata and omitted when unavailable.
- A missing feed blocks generation rather than pretending the feed is empty.
- The existing shell surrounds `/insights/subscribe` without modification.
- The 41 human-facing Subscribe destinations point to `/insights/subscribe`.
- Machine alternate links continue to point to `/feed.xml`.
- The feed browser view loads no analytics and therefore requires no consent
  banner.

The pre-existing typography-rule failures in the weekly briefing
(`research/gen_briefing.py` and its output) are outside this build and were not
touched.
