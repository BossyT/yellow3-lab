"""The site navigation, in one place.

WHY THIS FILE EXISTS. The nav is written into every page of this site - 631 of
them - and into three generators that write more. When it changed on 2026-08-05
(DPP added as a seventh item) it had to be swept across 629 pages by hand. The
same markup authored in four places is the shape of defect this repo has been
bitten by before: a number typed twice, a total that does not match its parts.

So the nav is defined here once. The generators import it, the static pages are
swept from it, and `--check` proves the site agrees with it. A page that drifts
is a failing check rather than something somebody notices in a screenshot.

    python3 research/site_nav.py --check     does every page match?
    python3 research/site_nav.py --apply     rewrite the ones that do not

THE ACTIVE ITEM IS PRESERVED, not guessed. Each page already says which nav item
it is on, and that is information the sweep must not lose - so the current
active item is read out of the page and mapped forward.
"""

import os
import re
import sys

# The menu, in order. Approved 2026-08-11: `Work` and the standalone `DPP` item
# are gone and `Thinking` is now `Insights`. Labels are written in sentence case
# and the stylesheet uppercases them - see .nav-mid a { text-transform:
# uppercase }. Writing them shouted in the markup would put the styling in two
# places and break the brand rule everywhere the CSS does not reach.
NAV_ITEMS = [
    ("/research", "Research"),
    ("/platforms", "Platforms"),
    ("/insights/", "Insights"),
    ("/advisory", "Advisory"),
    ("/about", "About"),
    # /contact from 2026-08-14, approved by GPT as a functional correction
    # rather than a navigation redesign. It had pointed at /#contact, and there
    # has never been an id="contact" on the homepage, so the menu item went to
    # the top of the homepage and did nothing. /contact is now a real page.
    ("/contact", "Contact"),
]

# Where a page that was active under the OLD menu belongs under the new one.
# `/naffe` is the only real decision here: naffe.ai is a platform, so a visitor
# reading it is inside Platforms. The DPP register keeps Research, because that
# is where it lives and what it is.
ACTIVE_MOVED = {
    "/naffe": "/platforms",
    "/research/digital-product-passport/suppliers": "/research",
    "/insights/": "/insights/",
    "/#contact": "/contact",
}

# The header CTA that the old menu carried on the homepage. Only this one label
# changes; pages that ask for contact, or point at naffe.ai, keep their own.
OLD_CTA = re.compile(
    r'(<a href="/naffe" class="nav-cta">)Explore our work(\s*<span)')
NEW_CTA = r'<a href="/research" class="nav-cta">View our research\2'

NAV_BLOCK = re.compile(r'(<div class="nav-mid"[^>]*>)(.*?)(</div>)', re.S)
ACTIVE_HREF = re.compile(r'<a href="([^"]+)"[^>]*class="active"')

# Pages that are not part of the public site and must not be swept. admin.html
# is the live CMS holding a token; it is changed only with an explicit
# go-ahead.
SKIP = {"admin.html", "google4b600ad4155228a3.html"}
SKIP_DIRS = {"node_modules", ".git", ".vercel", "Autonomous ai software"}


def render(active=None, indent="      "):
    """The nav-mid contents, with one item marked active."""
    out = []
    for href, label in NAV_ITEMS:
        cls = ' class="active"' if href == active else ""
        out.append(f'{indent}<a href="{href}"{cls}>{label}</a>')
    return "\n" + "\n".join(out) + "\n    "


# ---------------------------------------------------------------- the footer
#
# The footer is a separate component and is NOT redesigned here - only its
# information architecture, so it says the same things the menu says. Approved
# 2026-08-11: `Work` and `Thinking` are retired as structural headings, naffe.ai
# belongs under Platforms, and Advisory sits with the company rather than among
# the platforms.
#
# The middle Research column is deliberately untouched. It differs by page type
# (a model page lists the model work, the register lists the method) and that is
# contextual navigation, not architecture.

FOOT_WORK_COL = re.compile(
    r'(<div class="foot-col">\s*<h4>)Work(</h4>\s*)'
    r'<a href="/naffe">naffe\.ai</a>\s*'
    r'<a href="/research/digital-product-passport">Digital Product Passports</a>\s*'
    r'<a href="/advisory">Advisory</a>', re.S)

# naffe.ai first - it is the platform a reader of this footer is most likely to
# be looking for by name - then the register, then the page that explains why
# either exists. The Buyer Platform is NOT listed: it is surfaced on /platforms
# and from the DPP pages where its audience already is, and a footer link on
# every page of the site would start making yellow3 look like a DPP vendor.
FOOT_PLATFORMS_COL = (
    r'\1Platforms\2'
    r'<a href="/naffe">naffe.ai</a>\n'
    r'          <a href="/research/digital-product-passport/suppliers">DPP Supplier Register</a>\n'
    r'          <a href="/platforms">All platforms</a>')

# A link labelled naffe.ai goes to naffe.ai. Thomas, 2026-08-14, deciding the
# one ambiguous case in the /software handoff: the yellow3 page about the
# software is /software, and anything carrying the product's own name should
# reach the product. The old /naffe route redirects to /software for anyone
# holding an old link.
FOOT_NAFFE = re.compile(r'<a href="/naffe">naffe\.ai</a>')
FOOT_NAFFE_NEW = '<a href="https://naffe.ai/">naffe.ai</a>'

# The Platforms column, corrected 2026-08-15 on GPT's IA ruling.
#
# The DPP Supplier Register moves OUT of Platforms: it is a public research
# instrument, not a yellow3 product platform, and listing it as a platform
# misclassified it against the frozen site architecture. It moves into the
# Research column below.
#
# Software moves IN. Since a link labelled naffe.ai goes to naffe.ai, the
# footer's naffe entry leaves the site entirely, and /software - the yellow3
# page explaining why the company is building it - had no footer route at all.
#
# The DPP Buyer Platform stays out, for the reason recorded on 11 August: this
# footer renders on all 191 supplier profile pages, and a commercial Digital
# Product Passport product link on every page of an independent register works
# against the independence the register is built on.
FOOT_PLATFORMS_COLUMN = re.compile(
    r'(<div class="foot-col">\s*<h4>Platforms</h4>\s*)'
    r'<a href="https://naffe\.ai/">naffe\.ai</a>\s*'
    r'<a href="/research/digital-product-passport/suppliers">DPP Supplier Register</a>\s*'
    r'(<a href="/platforms">All platforms</a>)', re.S)
FOOT_PLATFORMS_NEW = (
    r'\1<a href="https://naffe.ai/">naffe.ai</a>\n'
    r'          <a href="/software">Software</a>\n'
    r'          \2')

# ...and the register arrives in Research, where it belongs.
#
# NOT a wholesale rewrite of that column. It carries three deliberate variants -
# the DPP family lists the method, the Model Adoption family lists the report -
# and site_nav has always left it alone because that is contextual navigation
# rather than architecture. The register is appended to whichever variant a page
# already has, so the reclassification happens without flattening 635 pages into
# one list.
FOOT_RESEARCH_COLUMN = re.compile(
    r'(<div class="foot-col">\s*<h4>Research</h4>(?:(?!</div>).)*?)(\s*</div>)', re.S)
REGISTER_LINK = ('\n          <a href="/research/digital-product-passport/suppliers">'
                 'DPP Supplier Register</a>')


def add_register_to_research(text):
    def one(m):
        body = m.group(1)
        if 'digital-product-passport/suppliers' in body:
            return m.group(0)
        return body + REGISTER_LINK + m.group(2)
    return FOOT_RESEARCH_COLUMN.sub(one, text, count=1)

FOOT_THINKING = re.compile(r'(<a href="/insights/"[^>]*>)Thinking(</a>)')

# Advisory left the first column, so it joins the company links.
#
# SCOPED TO THE COMPANY COLUMN, and it has to be. The first version matched the
# first `About` link in the document, which is the one in the NAV - so every
# page got a second Advisory item in its menu. Caught by reading a swept page,
# not by the sweep, which reported success on all 630.
FOOT_COMPANY_COL = re.compile(
    r'(<div class="foot-col">\s*<h4>Company</h4>.*?)(</div>)', re.S)
FOOT_ABOUT = re.compile(r'(<a href="/about">About</a>)(\s*)')

# The footer's Contact item, in the two forms it had drifted into: 537 pages
# sent it to /advisory, which is a different thing and not a front door, and 96
# sent it to an href="#" that assembles a mailto in an onclick - dead without
# JavaScript and read as a dead link by a screen reader. Approved 2026-08-14:
# both become /contact. The separate "Email us" action in the contact column is
# deliberately left alone; it is meant to be a direct email.
FOOT_CONTACT = re.compile(
    r'<a href="(?:/advisory|#)"(?:\s+onclick="[^"]*")?\s*>Contact</a>')
FOOT_CONTACT_NEW = '<a href="/contact">Contact</a>'

# The footer's identity block. "Copenhagen AI Lab" defined the company as an
# AI-only studio, which every current entity contract rules out, and the freeze
# protects the approved design - not copy that has since been superseded.
# Approved 2026-08-14. Structure, typography and geometry are untouched: this is
# the text inside two existing elements and nothing else. The label is written
# in sentence case because .fb-lab already uppercases it - writing it shouted
# here would put the styling in two places and break the brand rule wherever
# the CSS does not reach.
FOOT_IDENTITY = re.compile(
    r'(<div class="fb-lab">)Copenhagen AI Lab(</div>\s*<p>)'
    r'Building outcome infrastructure for the AI era\.(</p>)')
FOOT_IDENTITY_NEW = (
    r'\1yellow3 lab\2'
    r'We use emerging technology to make business less complicated.\3')


def sweep_footer(text):
    """Footer information architecture, matching the menu. Layout untouched."""
    out = FOOT_WORK_COL.sub(FOOT_PLATFORMS_COL, text)
    out = FOOT_THINKING.sub(r'\1Insights\2', out)
    out = FOOT_CONTACT.sub(FOOT_CONTACT_NEW, out)
    out = FOOT_NAFFE.sub(FOOT_NAFFE_NEW, out)
    out = FOOT_PLATFORMS_COLUMN.sub(FOOT_PLATFORMS_NEW, out)
    out = add_register_to_research(out)
    out = FOOT_IDENTITY.sub(FOOT_IDENTITY_NEW, out)

    def company(match):
        block, close = match.group(1), match.group(2)
        if '>Advisory</a>' in block:
            return block + close
        return FOOT_ABOUT.sub(
            r'\1\2<a href="/advisory">Advisory</a>\2', block, count=1) + close

    return FOOT_COMPANY_COL.sub(company, out, count=1)


def _html_files(root):
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in sorted(files):
            if name.endswith(".html") and name not in SKIP:
                yield os.path.join(base, name)


def nav_faults(text):
    """Anything wrong with a page's menu, in words.

    THE FOOTER SWEEP ONCE EDITED THE MENU. Its Advisory insertion matched the
    first `About` link in the document, which is the one in the nav, so every
    page gained a second Advisory item - and the sweep reported success on all
    630 because it only compared the nav block it had just written. A rewrite
    that is checked against itself proves nothing, so the page is now read back
    and asked plain questions instead.
    """
    faults = []
    match = NAV_BLOCK.search(text)
    if not match:
        return faults
    block = match.group(2)
    for href, label in NAV_ITEMS:
        seen = block.count(f'href="{href}"')
        if seen != 1:
            faults.append(f'{label} appears {seen} times in the menu')
    extra = len(re.findall(r'<a ', block)) - len(NAV_ITEMS)
    if extra:
        faults.append(f'{extra} menu item(s) that are not in NAV_ITEMS')
    if block.count('class="active"') > 1:
        faults.append('more than one active item')
    return faults


def footer_faults(text):
    """Anything wrong with a page's footer identity, read back off disk.

    Same reason nav_faults exists: the sweep must not be the thing that grades
    the sweep. These read the file as it now stands and ask whether the retired
    copy and the retired Contact targets are really gone.
    """
    faults = []
    if 'class="site-footer"' not in text and 'class="fb-lab"' not in text \
            and '>Contact</a>' not in text:
        return faults
    if 'Copenhagen AI Lab' in text:
        faults.append('footer still says Copenhagen AI Lab')
    if 'Building outcome infrastructure for the AI era' in text:
        faults.append('footer still carries the retired tagline')
    for stale in re.finditer(r'<a href="(/advisory|#)"[^>]*>Contact</a>', text):
        faults.append(f'footer Contact still points at {stale.group(1)}')
    if '<a href="/naffe">naffe.ai</a>' in text:
        faults.append('a link labelled naffe.ai still points at /naffe')
    plat = re.search(r'<h4>Platforms</h4>((?:(?!</div>).)*)', text, re.S)
    if plat:
        if 'DPP Supplier Register' in plat.group(1):
            faults.append('the register is still listed as a platform')
        if '/software' not in plat.group(1):
            faults.append('Software is missing from the Platforms column')
    res = re.search(r'<h4>Research</h4>((?:(?!</div>).)*)', text, re.S)
    if res and 'digital-product-passport/suppliers' not in res.group(1):
        faults.append('the register is missing from the Research column')
    return faults


def sweep(root, apply_changes):
    changed, checked = [], 0
    for path in _html_files(root):
        text = open(path, encoding="utf-8").read()
        match = NAV_BLOCK.search(text)
        if not match:
            continue
        checked += 1

        current = ACTIVE_HREF.search(match.group(2))
        active = current.group(1) if current else None
        # A page whose active item was removed moves to where it now belongs;
        # one whose item survived keeps it; one with none stays with none.
        active = ACTIVE_MOVED.get(active, active)
        if active not in [href for href, _ in NAV_ITEMS]:
            active = None

        rebuilt = NAV_BLOCK.sub(
            lambda m: m.group(1) + render(active) + m.group(3), text, count=1)
        rebuilt = OLD_CTA.sub(NEW_CTA, rebuilt)
        rebuilt = sweep_footer(rebuilt)

        if rebuilt != text:
            changed.append(os.path.relpath(path, root))
            if apply_changes:
                open(path, "w", encoding="utf-8").write(rebuilt)
    return checked, changed


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    apply_changes = "--apply" in sys.argv
    checked, changed = sweep(root, apply_changes)

    # Read back what is on disk, whether or not anything was rewritten.
    faults = []
    for path in _html_files(root):
        text = open(path, encoding="utf-8").read()
        for fault in nav_faults(text) + footer_faults(text):
            faults.append(f"{os.path.relpath(path, root)}: {fault}")

    # And the generators that write pages. Sweeping the output and leaving the
    # templates is how Google Analytics came back into 536 files in one command
    # on 2026-08-14: the pages were clean, the things that write the pages were
    # not, and the guard only ever read the pages. A copy correction is not
    # finished until the templates carry it too.
    gen_dir = os.path.join(root, "research")
    for name in sorted(os.listdir(gen_dir)):
        if not name.endswith(".py") or name == "site_nav.py":
            continue
        text = open(os.path.join(gen_dir, name), encoding="utf-8").read()
        for fault in footer_faults(text):
            faults.append(f"research/{name}: {fault} (in a generator template)")
    if faults:
        print(f"nav: {len(faults)} broken menu(s) or footer(s)")
        for fault in faults[:20]:
            print("  " + fault)
        if len(faults) > 20:
            print(f"  ... and {len(faults) - 20} more")
        return 1

    if apply_changes:
        print(f"nav: {checked} pages checked, {len(changed)} rewritten")
        return 0

    if changed:
        print(f"nav: {len(changed)} of {checked} pages do not match "
              f"research/site_nav.py")
        for name in changed[:20]:
            print("  " + name)
        if len(changed) > 20:
            print(f"  ... and {len(changed) - 20} more")
        print("\nRun: python3 research/site_nav.py --apply")
        return 1

    print(f"nav: {checked} pages, all match")
    return 0


if __name__ == "__main__":
    sys.exit(main())
