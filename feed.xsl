<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform" xmlns:media="http://search.yahoo.com/mrss/" xmlns:atom="http://www.w3.org/2005/Atom">
<xsl:output method="html" encoding="UTF-8" indent="yes" doctype-system="about:legacy-compat"/>
<xsl:template match="/">
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <title><xsl:value-of select="rss/channel/title"/></title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <meta name="robots" content="noindex"/>
  <link rel="preconnect" href="https://fonts.googleapis.com"/>
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin="crossorigin"/>
  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;1,400&amp;family=DM+Sans:wght@300;400;500&amp;display=swap"/>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: 'DM Sans', sans-serif; background: #ffffff; color: #444340; font-size: 16px; line-height: 1.7; padding: 80px 24px; -webkit-font-smoothing: antialiased; }
    .wrap { max-width: 720px; margin: 0 auto; }
    .eyebrow { font-size: 11px; letter-spacing: 0.18em; text-transform: uppercase; color: #aaa9a5; margin-bottom: 16px; }
    h1 { font-family: 'Playfair Display', serif; font-size: clamp(32px, 5vw, 48px); font-weight: 400; line-height: 1.15; color: #0f0f0e; margin-bottom: 24px; }
    .lede { font-size: 17px; color: #444340; max-width: 560px; margin-bottom: 32px; }
    .subscribe { background: #f7f6f3; border: 1px solid #e8e6e1; padding: 24px; border-radius: 4px; margin-bottom: 56px; font-size: 14px; }
    .subscribe strong { color: #0f0f0e; }
    .subscribe code { background: #ffffff; border: 1px solid #e8e6e1; padding: 4px 10px; border-radius: 3px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 13px; word-break: break-all; display: inline-block; margin-top: 8px; }
    .item { padding: 24px 0; border-top: 1px solid #e8e6e1; }
    .item:last-child { border-bottom: 1px solid #e8e6e1; }
    .item-date { font-size: 11px; letter-spacing: 0.16em; text-transform: uppercase; color: #aaa9a5; margin-bottom: 8px; }
    .item-title { font-family: 'Playfair Display', serif; font-size: 22px; font-weight: 400; line-height: 1.3; margin-bottom: 10px; }
    .item-title a { color: #0f0f0e; text-decoration: none; }
    .item-title a:hover { color: #888784; }
    .item-desc { font-size: 15px; color: #444340; line-height: 1.7; }
    .back { font-size: 12px; letter-spacing: 0.08em; text-transform: uppercase; color: #888784; text-decoration: none; border-bottom: 1px solid #e8e6e1; padding-bottom: 3px; transition: color 0.2s, border-color 0.2s; }
    .back:hover { color: #0f0f0e; border-color: #0f0f0e; }
    .footer-nav { margin-top: 56px; display: flex; gap: 24px; flex-wrap: wrap; }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="eyebrow">RSS feed</div>
    <h1><xsl:value-of select="rss/channel/title"/></h1>
    <p class="lede"><xsl:value-of select="rss/channel/description"/></p>
    <div class="subscribe">
      <strong>This is an RSS feed.</strong> To follow yellow3 insights, paste this URL into your feed reader (Feedly, Inoreader, NetNewsWire, Reeder, or any other RSS app):
      <br/>
      <code>https://yellow3.io/feed.xml</code>
    </div>
    <xsl:for-each select="rss/channel/item">
      <div class="item">
        <div class="item-date"><xsl:value-of select="substring(pubDate, 0, 17)"/></div>
        <h2 class="item-title"><a><xsl:attribute name="href"><xsl:value-of select="link"/></xsl:attribute><xsl:value-of select="title"/></a></h2>
        <p class="item-desc"><xsl:value-of select="description"/></p>
      </div>
    </xsl:for-each>
    <div class="footer-nav">
      <a class="back" href="/insights/">All insights</a>
      <a class="back" href="/">yellow3 lab</a>
    </div>
  </div>
</body>
</html>
</xsl:template>
</xsl:stylesheet>
