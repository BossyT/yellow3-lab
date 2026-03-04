# TASK: Deploy "Your Software Should Work While You Sleep" to yellow3.io

## Context
New thought leadership article for yellow3.io/insights. Article is fully written and styled to match existing site design (Cormorant Garamond + Manrope, same nav/footer, same CSS variables).

## Repo
- GitHub: BossyT/yellow3-lab (public)
- Vercel project: yellow3 (auto-deploys from main)
- Static HTML site, no build step

## Files to Add/Update

### ADD: insights/autonomous-ai-software.html
Full article HTML. Copy from the file provided.

### ADD: insights/og-autonomous-ai-software.png
OG image for social sharing (1536x1024). Copy from file provided.

### UPDATE: insights/index.html
Add new article card at the TOP of the articles list (before the AI Platform Costs article). The card HTML:

```html
<!-- ARTICLE 3 -->
<a href="/insights/autonomous-ai-software" class="article-card">
    <div class="article-meta">
        <span>March 2026</span>
        <span class="tag">Thought Leadership</span>
    </div>
    <h2>Your Software Should Work While You Sleep</h2>
    <p class="excerpt">Why autonomous AI software will save the average small business $20,000-$40,000 per year, generate $156,000 in extra revenue, and why 94% of companies aren't there yet.</p>
    <span class="read-more">Read article &rarr;</span>
</a>
```

### UPDATE: sitemap.xml
Add entry:
```xml
<url>
    <loc>https://yellow3.io/insights/autonomous-ai-software</loc>
    <lastmod>2026-03-04</lastmod>
    <priority>0.8</priority>
</url>
```

## DO NOT TOUCH
- index.html (homepage)
- insights/europes-ai-slumber.html
- insights/ai-platform-costs-2026.html
- logo.png / logo (1).png
- admin.html
- Any existing OG images

## Verification
After push, confirm:
1. https://yellow3.io/insights/ shows the new article card at top
2. https://yellow3.io/insights/autonomous-ai-software loads correctly
3. OG meta tags resolve for LinkedIn sharing
