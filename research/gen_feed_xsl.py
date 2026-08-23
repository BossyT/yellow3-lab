#!/usr/bin/env python3
"""
The approved browser presentation for /feed.xml.

WHAT THIS IS. 03-RSS-BROWSER-SPEC.md of the v1.0 handover puts the human layer
ON the feed rather than beside it: /feed.xml stays a valid RSS 2.0 document, and
the presentation is an XSLT stylesheet the browser applies to it. A reader gets
XML. A person gets the approved layout, rendered from the same channel and item
data. There is no second entry list to keep in step, and no production
/feed-preview route - Lock 02 is explicit that the prototype's route was a
design reference only.

THE SHELL IS HERE ON A RATIFIED v1.1 OVERRIDE. v1.0's
03-RSS-BROWSER-SPEC.md "Visual boundary" gave this presentation no yellow3 top
menu, no footer and no logo. Thomas asked for the menu and the footer on
23 August 2026, naming this URL; GPT ratified it the same day as handover v1.1,
superseding that boundary FOR THE FEED VIEW ONLY and replacing the two
acceptance checks that used to pass by absence. v1.0 is not rewritten. The
decision record is research/approved/insights-subscribe-v1.1.md, and the two
replacement checks are asserted by research/build_check.py rather than left to
a reading.

WHY IT IS GENERATED. The stylesheet is the approved package stylesheet, carried
in whole and in source order. It is subject to the lesson
research/port_approved_css.py was written for: a component depends on rules that
never mention it, and a stylesheet filtered by eye loses the ones that look like
somebody else's. Nothing here decides which rules the feed view needs.

It IS scoped, under .fv1, and that became load-bearing the moment the shell
arrived: the two stylesheets share a document and disagree about --ink, --line,
--muted and --yellow, which the nav and footer read twenty-one times between
them. See scoped_package_css(). Both the nav and the footer markup and the shell
CSS are read out of insights/subscribe.html at generation time, so this page's
menu and footer cannot drift away from the ones the rest of the site carries.

FAILURE BEHAVIOUR. If this stylesheet fails to load or the browser does not
apply XSLT, the XML is still served and still valid - the presentation is a
layer, never a gate. An item missing an optional field omits that line rather
than showing an invented value.

    python3 research/gen_feed_xsl.py            write feed.xsl
    python3 research/gen_feed_xsl.py --check    fail if feed.xsl is stale
"""

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACKAGE = os.path.join(ROOT, "research", "approved", "insights-subscribe.approved")
TARGET = os.path.join(ROOT, "feed.xsl")
SHELL_PAGE = os.path.join(ROOT, "insights", "subscribe.html")

# The package stylesheet is scoped under this wrapper, exactly as
# /insights/subscribe scopes it under .is1, and for the same reason - see
# scoped_package_css() below.
WRAPPER = "fv1"

# The site shell's own measurements. .site-nav is position:fixed, so whatever
# sits at the top of the document is painted over unless it is cleared.
# Measured in headless Chrome on the built page, not assumed: 74.6px at desktop
# (16px padding each side + a 41.6px CTA + a 1px border) and 67px below 880px,
# where the padding drops to 14px and the CTA is display:none.
NAV_DESKTOP = "74.6px"
NAV_MOBILE = "67px"

# The opening beneath the fixed menu, GPT handover v1.1: the same rhythm the
# subscription page uses, so the two surfaces open alike.
CLEAR_DESKTOP = "38px"   # desktop and tablet
CLEAR_MOBILE = "26px"    # 560px and below


def _read(path):
    return open(path, encoding="utf-8").read()


def _xml_safe(markup):
    """HTML markup -> markup an XML parser will accept.

    XSLT is XML, and XML predefines only lt/gt/amp/apos/quot. `&copy;` in the
    footer's copyright line is a perfectly good HTML entity and an undefined
    entity error in XML, which would take the whole stylesheet down - and a
    broken stylesheet on /feed.xml is a broken page for every human who opens
    it. Numeric references mean the same thing to both.
    """
    named = {"&copy;": "&#169;", "&nbsp;": "&#160;", "&amp;": "&amp;",
             "&mdash;": "&#8212;", "&ndash;": "&#8211;", "&rarr;": "&#8594;"}
    for k, v in named.items():
        markup = markup.replace(k, v)
    left = re.findall(r"&(?!#\d+;|#x[0-9a-fA-F]+;|amp;|lt;|gt;|quot;|apos;)\w+;",
                      markup)
    if left:
        raise SystemExit("shell markup carries HTML entities XML cannot parse: "
                         + ", ".join(sorted(set(left))))
    return markup


def shell_css():
    """The site shell's stylesheet, from the page that already carries it.

    Read from insights/subscribe.html rather than retyped, so the menu and
    footer on /feed.xml cannot drift away from the menu and footer everywhere
    else. That page's shell block is itself a verbatim copy of
    insights/index.html.
    """
    page = _read(SHELL_PAGE)
    start = page.index("<style>") + len("<style>")
    end = page.index("/* >>> APPROVED")
    css = page[start:end].strip()
    if ".site-nav" not in css or ".site-footer" not in css:
        raise SystemExit("shell block in %s no longer holds the nav and footer"
                         % SHELL_PAGE)
    return css


def shell_markup():
    """The nav and the footer, lifted whole from the same page."""
    page = _read(SHELL_PAGE)
    nav = re.search(r'(<nav class="site-nav">.*?</nav>)', page, re.S)
    foot = re.search(r'(<footer class="site-footer">.*?</footer>)', page, re.S)
    if not nav or not foot:
        raise SystemExit("could not find the nav and footer in %s" % SHELL_PAGE)
    return _xml_safe(nav.group(1)), _xml_safe(foot.group(1))


def package_css():
    html = _read(PACKAGE)
    m = re.search(r"<style>(.*?)</style>", html, re.S)
    if not m:
        raise SystemExit("no stylesheet block in the approved package")
    css = m.group(1).strip()
    # CSS lives in XML text here. `<` and `&` would end the text node; the
    # package uses neither, and this asserts it rather than assuming it.
    if "<" in css or "&" in css:
        raise SystemExit("package CSS contains < or & - it cannot be inlined "
                         "into XSLT as text without escaping")
    return css


def scoped_package_css():
    """The package stylesheet, every selector prefixed with the wrapper.

    WHY THIS IS NOT OPTIONAL NOW. While the feed view had no shell it was a
    standalone document and the package CSS could sit at document level. With
    the menu and footer on the page the two stylesheets share a document, and
    they disagree about four tokens:

        --ink     shell #0e0e0e   package #171717
        --line    shell #e7e6e2   package #d5d7d7
        --muted   shell #8a8a8a   package #6b6b6b
        --yellow  shell #ffe000   package #ffe500

    The nav and the footer read --ink, --line and --yellow twenty-one times
    between them, so an unscoped package would repaint the CTA, every border
    and the shell's yellow - which is exactly the "do not alter the existing
    header or footer colour" half of Lock 01, and the site-wide yellow token
    half of Lock 04. Scoping keeps the signal yellow on the feed content and
    leaves the shell reading the site's own values.

    The transform is research/port_approved_css.py's, imported rather than
    reimplemented, so both surfaces scope the same stylesheet the same way and
    the declaration count is asserted here too.
    """
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from port_approved_css import split_rules, scope, count_decls

    out, source, ported = [], 0, 0
    for kind, prelude, body in split_rules(package_css()):
        if kind == "rule":
            source += count_decls(body)
            ported += count_decls(body)
            out.append("%s{%s}" % (scope(prelude, WRAPPER), body))
        else:
            out.append(prelude + "{")
            for k2, sel2, body2 in split_rules(body):
                if k2 != "rule":
                    raise SystemExit("nested at-rule in %s" % prelude)
                source += count_decls(body2)
                ported += count_decls(body2)
                out.append("%s{%s}" % (scope(sel2, WRAPPER), body2))
            out.append("}")
    if ported != source:
        raise SystemExit("declaration count drifted: %d -> %d" % (source, ported))
    return "\n".join(out)


# Approved production deviations, emitted AFTER the package stylesheet and never
# folded into it - the same rule research/port_approved_css.py follows, so the
# port stays a mechanical transform and a deviation stays a decision somebody
# can read.
#
# There is one, and it exists because of a difference between the prototype and
# production that the design intends: 03-RSS-BROWSER-SPEC.md requires "Every row
# links to the canonical article URL from the RSS item", while the prototype's
# feed-preview rows are plain text with no anchors at all. So the package has no
# rule for a link inside an entry, its only anchor rule is a{color:inherit}, and
# every title and arrow renders with the user agent's underline - which is not
# the approved appearance. This restores it. Returned to Thomas and GPT for
# ratification with the v1.0 delivery, 23 August 2026.
DEVIATIONS = """
.WRAP .feed-entries h2 a{text-decoration:none}
.WRAP .feed-entries .entry-arrow{text-decoration:none}

/* THE SHELL ON THIS PAGE, RATIFIED. GPT, handover v1.1, 23 August 2026:
   Thomas's instruction is approved as a v1.1 override that supersedes
   03-RSS-BROWSER-SPEC.md's "Visual boundary" FOR THE FEED VIEW ONLY. The
   existing yellow3 menu and footer stay, the shell keeps its own tokens, the
   package stays scoped beneath .fv1, signal yellow stays #FFE500, and no
   package token may repaint the menu or the footer. v1.0 is not rewritten -
   the decision record is research/approved/insights-subscribe-v1.1.md.

   THE OPENING, ruled in the same pass: the signal rule must not touch the menu
   border. The feed view now opens with the subscription page's rhythm - 38px
   of clear space under the menu at desktop and tablet, 26px under the mobile
   menu - and the 7px rule follows that space.

   The nav is position:fixed and is 74.6px tall above 880px, 67px below it,
   where its padding drops and the CTA is display:none. The clear space is
   ADDED to the nav height, never substituted for it. Three bands, because the
   nav changes height at 880px and the clear space changes at 560px:

       above 880px    74.6 + 38     desktop
       561 - 880px    67   + 38     tablet, shorter nav, same clear space
       to 560px       67   + 26     mobile

   Cleared on .feed-view and not .feed-view-intro, deliberately: the rule is
   absolutely positioned at the intro's top, so padding the intro would leave
   the rule behind the menu instead of below it. All internal feed-view
   geometry beneath the rule is untouched - the intro keeps its 52px opening,
   so rule to eyebrow stays at 45px. */
.WRAP.feed-view{padding-top:calc(NAV_DESKTOP + CLEAR_DESKTOP)}
@media (max-width:880px){.WRAP.feed-view{padding-top:calc(NAV_MOBILE + CLEAR_DESKTOP)}}
@media (max-width:560px){.WRAP.feed-view{padding-top:calc(NAV_MOBILE + CLEAR_MOBILE)}}
"""

# The approved copy, 05-CONTENT-CONTRACT.md, "RSS browser presentation".
EYEBROW = "RSS 2.0 &#183; YELLOW3 INSIGHTS"
HEADLINE = "The publication feed."
EXPLANATION = ("This is a machine-readable RSS feed with a human browser "
               "presentation. Copy the address into your feed reader to receive "
               "new yellow3 Insights in chronological order.")
ADDRESS = "https://www.yellow3.io/feed.xml"

# Month names, spelled out and shouted, the way the approved entry metadata
# reads. XSLT 1.0 has no date parsing, so the RFC-822 pubDate is taken apart by
# delimiter rather than by offset - a single-digit day has no leading zero and
# fixed offsets would silently shift the whole string.
MONTHS = [("Jan", "JANUARY"), ("Feb", "FEBRUARY"), ("Mar", "MARCH"),
          ("Apr", "APRIL"), ("May", "MAY"), ("Jun", "JUNE"),
          ("Jul", "JULY"), ("Aug", "AUGUST"), ("Sep", "SEPTEMBER"),
          ("Oct", "OCTOBER"), ("Nov", "NOVEMBER"), ("Dec", "DECEMBER")]


def month_choose():
    out = ["        <xsl:choose>"]
    for abbr, full in MONTHS:
        out.append('          <xsl:when test="$m = \'%s\'">%s</xsl:when>'
                   % (abbr, full))
    out.append("          <xsl:otherwise><xsl:value-of select=\"$m\"/></xsl:otherwise>")
    out.append("        </xsl:choose>")
    return "\n".join(out)


TEMPLATE = '''<?xml version="1.0" encoding="UTF-8"?>
<!--
  The approved browser presentation for the yellow3 Insights feed, v1.0.

  GENERATED by research/gen_feed_xsl.py. Do not hand-edit: the stylesheet below
  is the approved package stylesheet, and a hand edit here is a change to an
  approved design that nothing would catch.

  This file only ever DECORATES /feed.xml. The feed is the canonical, valid RSS
  2.0 document at that address; feed readers never see any of this.

  THE TOP MENU AND FOOTER ON THIS PAGE ARE A RATIFIED v1.1 OVERRIDE. v1.0 gave
  this presentation no menu, no footer and no logo; GPT superseded that for the
  feed view on 23 August 2026, keeping the shell's own tokens and the feed
  presentation scoped beneath .fv1. See research/approved/insights-subscribe-v1.1.md.
-->
<xsl:stylesheet version="1.0"
                xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
                xmlns:atom="http://www.w3.org/2005/Atom"
                xmlns:media="http://search.yahoo.com/mrss/">
<xsl:output method="html" encoding="UTF-8" indent="yes"
            doctype-system="about:legacy-compat"/>

<!-- The publication date, spelled out. An item with no pubDate renders no date
     line at all, rather than an invented one. -->
<xsl:template name="pubdate">
  <xsl:param name="raw"/>
  <xsl:variable name="rest" select="normalize-space(substring-after($raw, ','))"/>
  <xsl:variable name="d" select="substring-before($rest, ' ')"/>
  <xsl:variable name="after" select="substring-after($rest, ' ')"/>
  <xsl:variable name="m" select="substring-before($after, ' ')"/>
  <xsl:variable name="y" select="substring-before(substring-after($after, ' '), ' ')"/>
  <xsl:if test="$d != '' and $m != ''">
    <xsl:value-of select="$d"/>
    <xsl:text> </xsl:text>
{MONTH_CHOOSE}
    <xsl:text> </xsl:text>
    <xsl:value-of select="$y"/>
  </xsl:if>
</xsl:template>

<xsl:template match="/">
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <!-- The canonical human route is /insights/subscribe. This endpoint is for
       machines, and it stays out of the index as it always has. -->
  <meta name="robots" content="noindex"/>
  <title><xsl:value-of select="rss/channel/title"/></title>
  <style>
/* ---------------------------------------------------------------------- */
/* THE SITE SHELL, read from insights/subscribe.html by                     */
/* research/gen_feed_xsl.py and emitted unaltered. It stays at document     */
/* level so the menu and the footer read the site's own tokens.             */
/* ---------------------------------------------------------------------- */
{SHELL_CSS}

/* ---------------------------------------------------------------------- */
/* THE APPROVED PACKAGE, every selector scoped under .{WRAPPER}. See        */
/* scoped_package_css() for why this is load-bearing rather than tidy.      */
/* ---------------------------------------------------------------------- */
{CSS}

/* Production deviations, appended after the package stylesheet and never
   folded into it. See the DEVIATIONS note in research/gen_feed_xsl.py. */
{DEVIATIONS}
  </style>
</head>
<body>

{NAV}

<main class="feed-view {WRAPPER}">

  <section class="feed-view-intro">
    <div class="signal-line" aria-hidden="true"></div>
    <div>
      <p class="kicker">{EYEBROW}</p>
      <h1>{HEADLINE}</h1>
    </div>
    <p>{EXPLANATION}</p>
  </section>

  <section class="feed-address-band">
    <span>FEED ADDRESS</span>
    <strong>{ADDRESS}</strong>
    <a href="/insights/subscribe">HOW TO SUBSCRIBE <span>&#8594;</span></a>
  </section>

  <section class="feed-entries" aria-label="Feed entries">
    <xsl:for-each select="rss/channel/item">
      <article>
        <p class="entry-index"><xsl:number format="01" value="position()"/></p>
        <div>
          <xsl:if test="normalize-space(pubDate) != ''">
            <p class="entry-meta">
              <xsl:call-template name="pubdate">
                <xsl:with-param name="raw" select="pubDate"/>
              </xsl:call-template>
            </p>
          </xsl:if>
          <h2>
            <xsl:choose>
              <xsl:when test="normalize-space(link) != ''">
                <a>
                  <xsl:attribute name="href"><xsl:value-of select="link"/></xsl:attribute>
                  <xsl:value-of select="title"/>
                </a>
              </xsl:when>
              <xsl:otherwise><xsl:value-of select="title"/></xsl:otherwise>
            </xsl:choose>
          </h2>
          <xsl:if test="normalize-space(description) != ''">
            <p><xsl:value-of select="description"/></p>
          </xsl:if>
        </div>
        <xsl:if test="normalize-space(link) != ''">
          <a class="entry-arrow" aria-hidden="true">
            <xsl:attribute name="href"><xsl:value-of select="link"/></xsl:attribute>
            <xsl:text>&#8594;</xsl:text>
          </a>
        </xsl:if>
      </article>
    </xsl:for-each>
  </section>

</main>

{FOOTER}

</body>
</html>
</xsl:template>
</xsl:stylesheet>
'''


def build():
    return (TEMPLATE
            .replace("{MONTH_CHOOSE}", month_choose())
            .replace("{SHELL_CSS}", shell_css())
            .replace("{CSS}", scoped_package_css())
            .replace("{DEVIATIONS}", DEVIATIONS.strip()
                     .replace(".WRAP", "." + WRAPPER)
                     .replace("NAV_DESKTOP", NAV_DESKTOP)
                     .replace("NAV_MOBILE", NAV_MOBILE)
                     .replace("CLEAR_DESKTOP", CLEAR_DESKTOP)
                     .replace("CLEAR_MOBILE", CLEAR_MOBILE))
            .replace("{NAV}", shell_markup()[0])
            .replace("{FOOTER}", shell_markup()[1])
            .replace("{WRAPPER}", WRAPPER)
            .replace("{EYEBROW}", EYEBROW)
            .replace("{HEADLINE}", HEADLINE)
            .replace("{EXPLANATION}", EXPLANATION)
            .replace("{ADDRESS}", ADDRESS))


def main():
    fresh = build()
    current = open(TARGET, encoding="utf-8").read() if os.path.exists(TARGET) else None

    if "--check" in sys.argv:
        if current != fresh:
            raise SystemExit("feed.xsl is stale - "
                             "run python3 research/gen_feed_xsl.py")
        print("  ok  feed.xsl: approved presentation, package stylesheet verbatim")
        return 0

    if current != fresh:
        open(TARGET, "w", encoding="utf-8").write(fresh)
        print("feed.xsl written")
    else:
        print("feed.xsl current")
    return 0


if __name__ == "__main__":
    sys.exit(main())
