#!/usr/bin/env python3
import html as html_lib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / 'data' / 'portal_data.json'
INDEX_TPL = ROOT / 'templates' / 'index_template.html'
POST_TPL = ROOT / 'templates' / 'post_template.html'
POSTS_DIR = ROOT / 'posts'
POSTS_DIR.mkdir(parents=True, exist_ok=True)

SITE_BASE_URL = 'https://latestjobalert.pages.dev'
TODAY_STR = datetime.now(timezone.utc).strftime('%Y-%m-%d')

def slugify(text, item_id):
    s = re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')
    s = re.sub(r'-+', '-', s)[:60].strip('-')
    return f"{s}-{item_id}"

def build_link_rows(it, sec_id):
    official_url = it.get('officialUrl') or 'https://india.gov.in/'
    p_url = it.get('primaryUrl') or official_url
    s_url = it.get('secondaryUrl') or official_url
    domain = official_url.replace('https://', '').replace('http://', '').strip('/')

    r1_label, r1_btn, r2_label, r2_btn = 'Apply Online', 'Apply Now', 'Download Official Notification', 'Click Here'
    if sec_id == 'admit':
        r1_label, r1_btn, r2_label = 'Download Admit Card / Exam City Slip', 'Download Admit Card', 'Exam Date & Instructions Notice'
    elif sec_id == 'result':
        r1_label, r1_btn, r2_label = 'Download Result / Score Card', 'Check Result', 'Cut-Off / Merit List PDF'
    elif sec_id == 'answer':
        r1_label, r1_btn, r2_label, r2_btn = 'Download Answer Key / Response Sheet', 'Download Answer Key', 'Raise Objection / Challenge Key', 'Objection Link'
    elif sec_id == 'correction':
        r1_label, r1_btn, r2_label, r2_btn = 'Form Correction / Edit / Finalize Link', 'Edit / Correct Form', 'Correction Window Notice', 'Click Here'
    elif sec_id == 'syllabus':
        r1_label, r1_btn, r2_label = 'Download Syllabus & Exam Pattern PDF', 'Download Syllabus', 'Official Exam Portal'
    elif sec_id == 'verification':
        r1_label, r1_btn, r2_label = 'Online Registration / Verification Portal', 'Open Portal', 'Check Application Status / Guidelines'

    return (
        f'<div class="flex items-center justify-between gap-2 px-4 py-3">'
        f'<span class="font-semibold text-xs sm:text-sm">{html_lib.escape(r1_label)}</span>'
        f'<a href="{html_lib.escape(p_url)}" target="_blank" rel="noopener noreferrer" class="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs shrink-0 transition">{html_lib.escape(r1_btn)} ↗</a>'
        f'</div>'
        f'<div class="flex items-center justify-between gap-2 px-4 py-3">'
        f'<span class="font-semibold text-xs sm:text-sm">{html_lib.escape(r2_label)}</span>'
        f'<a href="{html_lib.escape(s_url)}" target="_blank" rel="noopener noreferrer" class="px-4 py-2 rounded-lg bg-sky-600 hover:bg-sky-700 text-white font-bold text-xs shrink-0 transition">{html_lib.escape(r2_btn)} ↗</a>'
        f'</div>'
        f'<div class="flex items-center justify-between gap-2 px-4 py-3">'
        f'<span class="font-semibold text-xs sm:text-sm">Official Website</span>'
        f'<a href="{html_lib.escape(official_url)}" target="_blank" rel="noopener noreferrer" class="text-red-700 font-bold text-xs sm:text-sm hover:underline">{html_lib.escape(domain)}</a>'
        f'</div>'
    )

def main():
    data = json.loads(DATA_FILE.read_text(encoding='utf-8'))
    all_posts = []
    seen = set()

    def reg(it, cat_title, sec_id):
        if it.get('id') == 'hl-8':
            return
        slug = slugify(it['title'], it['id'])
        url = f"posts/{slug}.html"
        if it['id'] not in seen:
            seen.add(it['id'])
            all_posts.append((it, cat_title, sec_id, slug, url))

    for it in data.get('LAST_DATE_ITEMS', []):
        reg(it, 'Last Date Alert', 'lastDate')
    for it in data.get('CORRECTION_ITEMS', []):
        reg(it, 'Correction Date / Edit Form', 'correction')
    for it in data.get('HIGHLIGHTS', []):
        reg(it, 'Trending Form', 'jobs')
    for sec in data.get('SECTIONS', []):
        for it in sec.get('items', []):
            reg(it, sec['title'], sec['id'])

    post_url_map = {it['id']: url for it, _, _, _, url in all_posts}

    idx_html = INDEX_TPL.read_text(encoding='utf-8')
    idx_html = idx_html.replace('{{PORTAL_DATA_JSON}}', json.dumps(data, ensure_ascii=False))
    idx_html = idx_html.replace('{{POST_URL_MAP_JSON}}', json.dumps(post_url_map, ensure_ascii=False))
    (ROOT / 'index.html').write_text(idx_html, encoding='utf-8')

    post_tpl_str = POST_TPL.read_text(encoding='utf-8')
    for it, cat_title, sec_id, slug, url in all_posts:
        dates = it.get('dates') or {}
        related = [x for x in all_posts if x[0]['id'] != it['id'] and x[2] == sec_id][:6]
        rel_html = '\n'.join(
            f'<li class="px-4 py-3 hover:bg-slate-50"><a href="{x[3]}.html" class="text-xs sm:text-sm font-medium text-slate-800 hover:text-red-700 flex items-center justify-between"><span>• {html_lib.escape(x[0]["title"])}</span><span>›</span></a></li>'
            for x in related
        ) or '<li class="px-4 py-3 text-xs text-slate-500">More updates coming soon.</li>'

        json_ld = json.dumps({
            '@context': 'https://schema.org',
            '@type': 'NewsArticle',
            'headline': it['title'],
            'datePublished': TODAY_STR,
            'dateModified': TODAY_STR,
            'author': {'@type': 'Organization', 'name': 'Latest Job Alert'}
        })

        p_html = (
            post_tpl_str
            .replace('{{TITLE}}', html_lib.escape(it['title']))
            .replace('{{META_DESC}}', html_lib.escape((it.get('shortInfo') or it['title'])[:155]))
            .replace('{{CATEGORY}}', html_lib.escape(cat_title))
            .replace('{{UPDATED_DATE}}', TODAY_STR)
            .replace('{{SHORT_INFO}}', html_lib.escape(it.get('shortInfo') or it['title']))
            .replace('{{DATE_START}}', html_lib.escape(dates.get('start', 'Check Portal')))
            .replace('{{DATE_LAST}}', html_lib.escape(dates.get('lastDate', 'Check Portal')))
            .replace('{{DATE_EXAM}}', html_lib.escape(dates.get('examDate', 'Notified Soon')))
            .replace('{{FEE}}', html_lib.escape(it.get('fee') or 'As per Official Notice'))
            .replace('{{AGE}}', html_lib.escape(it.get('age') or 'As per Govt Rules'))
            .replace('{{VACANCIES}}', html_lib.escape(it.get('vacancies') or 'See Notification'))
            .replace('{{OFFICIAL_LINK_ROWS}}', build_link_rows(it, sec_id))
            .replace('{{RELATED_ITEMS_HTML}}', rel_html)
            .replace('{{JSON_LD}}', json_ld)
        )
        (POSTS_DIR / f"{slug}.html").write_text(p_html, encoding='utf-8')

    legal = {
        'about.html': ('About Us — Latest Job Alert', 'Latest Job Alert is an independent Indian government job, admit card, result, and exam notification portal with direct official .gov.in / .nic.in links and GreenPix Labs tools.'),
        'contact.html': ('Contact Us — Latest Job Alert', 'Reach out via our official YouTube channel (@officiallatestjobalert) or community channels.'),
        'privacy.html': ('Privacy Policy — Latest Job Alert', 'Bookmarks are stored locally in your browser. Advertising partners such as Google AdSense may use cookies to serve relevant ads.'),
        'disclaimer.html': ('Disclaimer — Latest Job Alert', 'Latest Job Alert is not affiliated with any government body. Always verify details on the official government website before applying.')
    }
    for fname, (ptitle, pbody) in legal.items():
        (ROOT / fname).write_text(
            f'<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{ptitle}</title><script src="https://cdn.tailwindcss.com/3.4.17"></script></head><body class="bg-slate-50 text-slate-900 p-6 font-sans"><div class="max-w-3xl mx-auto bg-white rounded-2xl border p-6 shadow-sm space-y-3"><a href="index.html" class="text-xs font-bold text-red-700">← Back to Home</a><h1 class="text-2xl font-extrabold">{ptitle}</h1><p class="text-sm text-slate-700 leading-relaxed">{pbody}</p></div></body></html>',
            encoding='utf-8'
        )

    urls = ['index.html', 'about.html', 'contact.html', 'privacy.html', 'disclaimer.html'] + [u for _, _, _, _, u in all_posts]
    sitemap_entries = '\n'.join(f'  <url><loc>{SITE_BASE_URL}/{u}</loc><lastmod>{TODAY_STR}</lastmod></url>' for u in urls)
    (ROOT / 'sitemap.xml').write_text(f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{sitemap_entries}\n</urlset>\n', encoding='utf-8')
    (ROOT / 'robots.txt').write_text(f'User-agent: *\nAllow: /\nSitemap: {SITE_BASE_URL}/sitemap.xml\n', encoding='utf-8')
    print(f'Built index.html + {len(all_posts)} SEO post pages + sitemap.xml!')

if __name__ == '__main__':
    main()
