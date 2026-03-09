const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const DOMAIN = 'https://yellow3.io';
const EXCLUDE = ['admin.html', 'google4b600ad4155228a3.html'];
const EXCLUDE_DIRS = ['Autonomous ai software', 'node_modules', '.git', '.vercel'];

function getHtmlFiles(dir, base = '') {
  const files = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (EXCLUDE_DIRS.includes(entry.name)) continue;
    const rel = path.join(base, entry.name);
    if (entry.isDirectory()) {
      files.push(...getHtmlFiles(path.join(dir, entry.name), rel));
    } else if (entry.name.endsWith('.html') && !EXCLUDE.includes(entry.name)) {
      files.push(rel);
    }
  }
  return files;
}

function getLastMod(file) {
  try {
    const date = execSync(`git log -1 --format=%aI -- "${file}"`, { encoding: 'utf8' }).trim();
    return date ? date.slice(0, 10) : new Date().toISOString().slice(0, 10);
  } catch {
    return new Date().toISOString().slice(0, 10);
  }
}

function getPriority(urlPath) {
  if (urlPath === '/') return '1.0';
  if (urlPath === '/insights/' || urlPath === '/masterclass') return '0.9';
  if (urlPath.startsWith('/insights/')) return '0.8';
  return '0.5';
}

function getFrequency(urlPath) {
  if (urlPath === '/insights/' || urlPath === '/insights') return 'weekly';
  return 'monthly';
}

function fileToUrl(file) {
  let url = '/' + file.replace(/\\/g, '/');
  if (url.endsWith('/index.html')) {
    url = url.replace('/index.html', '/');
  } else {
    url = url.replace('.html', '');
  }
  if (url === '/') return '/';
  return url;
}

const root = __dirname;
const files = getHtmlFiles(root).sort();

const urls = files.map(file => {
  const urlPath = fileToUrl(file);
  return {
    loc: DOMAIN + urlPath,
    lastmod: getLastMod(file),
    changefreq: getFrequency(urlPath),
    priority: getPriority(urlPath),
  };
});

const xml = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${urls.map(u => `    <url>
        <loc>${u.loc}</loc>
        <lastmod>${u.lastmod}</lastmod>
        <changefreq>${u.changefreq}</changefreq>
        <priority>${u.priority}</priority>
    </url>`).join('\n')}
</urlset>
`;

fs.writeFileSync(path.join(root, 'sitemap.xml'), xml);
console.log(`Sitemap generated with ${urls.length} URLs`);
