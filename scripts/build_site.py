#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build a static videos-only site from BookIndex catalog + pipeline.

Reads (sibling clone layout, override with env):
  BOOKINDEX_ROOT/app_data.json          → video_catalog
  BOOKINDEX_ROOT/data/video_pipeline.json → stages, themes

Writes into repo root:
  index.html
  video/<id>/index.html
  data/catalog.json
  data/stats.json
  sitemap.xml
  .nojekyll

One page per unique YouTube id. Multi-title collisions keep all titles on the
survivor page and flag data_quality.collisions.
"""
from __future__ import annotations

import html
import json
import os
import re
import sys
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
BOOKINDEX = Path(
    os.environ.get(
        "BOOKINDEX_ROOT",
        str(ROOT.parent / "BookIndex"),
    )
)
SITE_BASE = os.environ.get(
    "SITE_BASE",
    "https://gasyoun.github.io/ZalizniakVideo",
).rstrip("/")
BOOKINDEX_VIDEO = (
    "https://gasyoun.github.io/BookIndex/aaz-index.html#v4/materials/video"
)
BOOKINDEX_VIDEO_DETAIL = (
    "https://gasyoun.github.io/BookIndex/aaz-index.html#v4/materials/video/{id}"
)
TODAY = date.today().isoformat()
BUILT_AT = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

CSS = """
:root {
  --bg: #f7f1e6;
  --ink: #2a1f12;
  --muted: #6b5640;
  --card: #fffdf8;
  --line: #d9c9b0;
  --accent: #8c3a15;
  --accent-soft: #f0e0d0;
  --link: #6b2e10;
  --warn: #8a4b00;
  --ok: #2f5d3a;
  --radius: 10px;
  --max: 52rem;
  --font: "Segoe UI", system-ui, -apple-system, sans-serif;
}
* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
  margin: 0;
  font-family: var(--font);
  color: var(--ink);
  background: var(--bg);
  line-height: 1.55;
}
a { color: var(--link); }
a:hover { color: var(--accent); }
a:focus-visible, button:focus-visible, input:focus-visible, select:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}
.wrap { max-width: var(--max); margin: 0 auto; padding: 1.25rem 1rem 3rem; }
header.site {
  border-bottom: 1px solid var(--line);
  background: linear-gradient(180deg, #fffaf1, var(--bg));
  margin-bottom: 1.25rem;
}
header.site .wrap { padding-bottom: 1rem; }
.brand { font-size: 0.85rem; color: var(--muted); letter-spacing: 0.02em; }
h1 { font-size: clamp(1.45rem, 3vw, 1.9rem); margin: 0.2rem 0 0.4rem; line-height: 1.25; }
.lede { color: var(--muted); margin: 0 0 0.75rem; max-width: 40rem; }
.meta-bar {
  display: flex; flex-wrap: wrap; gap: 0.5rem 0.85rem;
  font-size: 0.92rem; color: var(--muted);
}
.meta-bar strong { color: var(--ink); font-weight: 600; }
.controls {
  display: grid;
  grid-template-columns: 1fr;
  gap: 0.65rem;
  margin: 1rem 0 0.75rem;
  position: sticky;
  top: 0;
  z-index: 2;
  background: color-mix(in srgb, var(--bg) 92%, white);
  padding: 0.65rem 0;
  border-bottom: 1px solid var(--line);
}
@media (min-width: 640px) {
  .controls { grid-template-columns: 1.4fr 0.8fr 0.8fr; align-items: end; }
}
label { display: block; font-size: 0.8rem; color: var(--muted); margin-bottom: 0.2rem; }
input[type="search"], select {
  width: 100%;
  padding: 0.55rem 0.7rem;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--card);
  color: var(--ink);
  font: inherit;
}
#result-count[role="status"] { font-size: 0.9rem; color: var(--muted); min-height: 1.3em; }
.list { list-style: none; margin: 0; padding: 0; display: grid; gap: 0.55rem; }
.card {
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 0.75rem 0.9rem;
  display: grid;
  gap: 0.25rem;
}
.card a.title {
  font-weight: 600;
  text-decoration: none;
  color: var(--ink);
  font-size: 1.02rem;
}
.card a.title:hover { color: var(--accent); text-decoration: underline; }
.card .row { font-size: 0.88rem; color: var(--muted); display: flex; flex-wrap: wrap; gap: 0.35rem 0.75rem; }
.chip {
  display: inline-block;
  font-size: 0.75rem;
  padding: 0.12rem 0.45rem;
  border-radius: 999px;
  background: var(--accent-soft);
  color: var(--accent);
  border: 1px solid color-mix(in srgb, var(--accent) 25%, var(--line));
}
.chip.warn { background: #fff1d6; color: var(--warn); }
.empty {
  display: none;
  padding: 1.25rem;
  border: 1px dashed var(--line);
  border-radius: var(--radius);
  color: var(--muted);
  background: var(--card);
}
.empty.show { display: block; }
.player {
  position: relative;
  width: 100%;
  aspect-ratio: 16 / 9;
  background: #1a120a;
  border-radius: var(--radius);
  overflow: hidden;
  border: 1px solid var(--line);
  margin: 1rem 0;
}
.player iframe {
  position: absolute; inset: 0; width: 100%; height: 100%; border: 0;
}
.actions { display: flex; flex-wrap: wrap; gap: 0.5rem; margin: 0.75rem 0 1rem; }
.btn {
  display: inline-flex; align-items: center; gap: 0.35rem;
  padding: 0.5rem 0.85rem;
  border-radius: 8px;
  border: 1px solid var(--line);
  background: var(--card);
  color: var(--ink);
  text-decoration: none;
  font-size: 0.92rem;
}
.btn.primary {
  background: var(--accent);
  border-color: var(--accent);
  color: #fff;
}
.btn.primary:hover { filter: brightness(1.05); color: #fff; }
.section { margin: 1.25rem 0; }
.section h2 { font-size: 1.1rem; margin: 0 0 0.5rem; }
.entities { display: flex; flex-wrap: wrap; gap: 0.35rem; }
.entity {
  font-size: 0.8rem;
  padding: 0.2rem 0.5rem;
  border-radius: 6px;
  background: #efe6d7;
  border: 1px solid var(--line);
}
.entity .t { color: var(--muted); margin-left: 0.25rem; font-variant-numeric: tabular-nums; }
.crumbs { font-size: 0.9rem; color: var(--muted); margin-bottom: 0.5rem; }
.crumbs a { color: var(--muted); }
.note {
  font-size: 0.88rem;
  color: var(--muted);
  border-left: 3px solid var(--line);
  padding: 0.35rem 0 0.35rem 0.75rem;
  margin: 0.75rem 0;
}
footer.site {
  margin-top: 2.5rem;
  padding-top: 1rem;
  border-top: 1px solid var(--line);
  font-size: 0.85rem;
  color: var(--muted);
}
footer.site a { color: var(--muted); }
.hidden { display: none !important; }
@media (prefers-reduced-motion: reduce) {
  html { scroll-behavior: auto; }
}
"""

INDEX_JS = """
(function () {
  const list = document.getElementById('video-list');
  const cards = Array.from(list.querySelectorAll('[data-card]'));
  const q = document.getElementById('q');
  const theme = document.getElementById('theme');
  const sort = document.getElementById('sort');
  const count = document.getElementById('result-count');
  const empty = document.getElementById('empty');

  function norm(s) { return (s || '').toLowerCase().replace(/ё/g, 'е'); }

  function apply() {
    const query = norm(q.value.trim());
    const th = theme.value;
    let visible = cards.slice();

    visible.forEach(function (el) {
      const hay = el.getAttribute('data-search') || '';
      const elTheme = el.getAttribute('data-theme') || '';
      const okQ = !query || hay.indexOf(query) !== -1;
      const okT = !th || elTheme === th;
      el.classList.toggle('hidden', !(okQ && okT));
    });

    visible = cards.filter(function (el) { return !el.classList.contains('hidden'); });

    const mode = sort.value;
    visible.sort(function (a, b) {
      if (mode === 'duration-desc') {
        return (Number(b.dataset.duration) || 0) - (Number(a.dataset.duration) || 0);
      }
      if (mode === 'duration-asc') {
        return (Number(a.dataset.duration) || 0) - (Number(b.dataset.duration) || 0);
      }
      if (mode === 'date-desc') {
        return (b.dataset.date || '').localeCompare(a.dataset.date || '');
      }
      if (mode === 'date-asc') {
        return (a.dataset.date || '').localeCompare(b.dataset.date || '');
      }
      return (a.dataset.title || '').localeCompare(b.dataset.title || '', 'ru');
    });
    visible.forEach(function (el) { list.appendChild(el); });

    count.textContent = 'Показано: ' + visible.length + ' из ' + cards.length;
    empty.classList.toggle('show', visible.length === 0);
  }

  q.addEventListener('input', apply);
  theme.addEventListener('change', apply);
  sort.addEventListener('change', apply);
  apply();
})();
"""


def esc(s: Any) -> str:
    return html.escape("" if s is None else str(s), quote=True)


def fmt_duration(sec: Any) -> str:
    try:
        s = int(sec or 0)
    except (TypeError, ValueError):
        return "—"
    if s <= 0:
        return "—"
    h, rem = divmod(s, 3600)
    m, s2 = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s2:02d}"
    return f"{m}:{s2:02d}"


def youtube_id_from_url(url: str) -> str | None:
    if not url:
        return None
    m = re.search(r"(?:v=|youtu\.be/|embed/|shorts/)([A-Za-z0-9_-]{6,})", url)
    return m.group(1) if m else None


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def merge_catalog(catalog: list[dict], pipeline: dict) -> tuple[list[dict], dict]:
    pipe_by_id: dict[str, dict] = {}
    for v in pipeline.get("videos") or []:
        vid = v.get("id") or youtube_id_from_url(v.get("youtube_url") or "")
        if vid:
            pipe_by_id[vid] = v

    by_id: dict[str, dict] = {}
    title_collisions: dict[str, list[str]] = defaultdict(list)

    for row in catalog:
        rid = row.get("id") or youtube_id_from_url(row.get("url") or "")
        if not rid:
            continue
        title = (row.get("title") or "").strip() or rid
        title_collisions[rid].append(title)
        cur = by_id.get(rid)
        rel = row.get("related_entities") or []
        if cur is None:
            by_id[rid] = {
                "id": rid,
                "title": title,
                "url": row.get("url") or f"https://www.youtube.com/watch?v={rid}",
                "date": row.get("date") or None,
                "duration": int(row.get("duration") or 0),
                "timecodes": row.get("timecodes") or [],
                "related_entities": list(rel),
                "titles_all": [title],
            }
        else:
            if title not in cur["titles_all"]:
                cur["titles_all"].append(title)
            # Keep richest related_entities
            if len(rel) > len(cur.get("related_entities") or []):
                cur["related_entities"] = list(rel)
                cur["title"] = title
            if not cur.get("date") and row.get("date"):
                cur["date"] = row["date"]
            if int(row.get("duration") or 0) > int(cur.get("duration") or 0):
                cur["duration"] = int(row["duration"])

    # Ensure pipeline-only videos appear
    for rid, pv in pipe_by_id.items():
        if rid not in by_id:
            by_id[rid] = {
                "id": rid,
                "title": (pv.get("title") or rid).strip(),
                "url": pv.get("youtube_url") or f"https://www.youtube.com/watch?v={rid}",
                "date": None,
                "duration": int(pv.get("duration_sec") or 0),
                "timecodes": [],
                "related_entities": [],
                "titles_all": [(pv.get("title") or rid).strip()],
            }

    videos: list[dict] = []
    collisions = []
    for rid, item in by_id.items():
        titles = item["titles_all"]
        uniq_titles = []
        seen = set()
        for t in titles:
            k = t.casefold()
            if k not in seen:
                seen.add(k)
                uniq_titles.append(t)
        item["titles_all"] = uniq_titles
        item["collision"] = len(uniq_titles) > 1
        if item["collision"]:
            collisions.append({"id": rid, "titles": uniq_titles})

        pv = pipe_by_id.get(rid) or {}
        item["theme"] = pv.get("theme") or None
        item["stage"] = pv.get("stage") or None
        item["purpose"] = pv.get("purpose") or None
        item["transcription_quality"] = None
        tr = pv.get("transcription")
        if isinstance(tr, dict):
            item["transcription_quality"] = tr.get("quality")
        elif isinstance(tr, str):
            item["transcription_quality"] = tr
        if not item.get("duration") and pv.get("duration_sec"):
            item["duration"] = int(pv["duration_sec"])
        if not item.get("url") and pv.get("youtube_url"):
            item["url"] = pv["youtube_url"]

        # Path slug = YouTube id (stable)
        item["path"] = f"video/{rid}/"
        videos.append(item)

    videos.sort(key=lambda v: (v.get("title") or "").casefold())
    meta = {
        "raw_catalog_rows": len(catalog),
        "unique_videos": len(videos),
        "pipeline_videos": len(pipeline.get("videos") or []),
        "collisions": collisions,
        "pipeline_stats": pipeline.get("stats") or {},
        "built_at": BUILT_AT,
        "source": {
            "catalog": "BookIndex/app_data.json → video_catalog",
            "pipeline": "BookIndex/data/video_pipeline.json",
        },
    }
    return videos, meta


def page_shell(
    *,
    title: str,
    description: str,
    canonical: str,
    body: str,
    extra_head: str = "",
    scripts: str = "",
) -> str:
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
<meta name="robots" content="index, follow">
<link rel="canonical" href="{esc(canonical)}">
<meta property="og:type" content="website">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(description)}">
<meta property="og:url" content="{esc(canonical)}">
<meta name="theme-color" content="#8c3a15">
<style>{CSS}</style>
{extra_head}
</head>
<body>
{body}
{scripts}
</body>
</html>
"""


def footer_html() -> str:
    return f"""
<footer class="site wrap">
  <p>Каталог публичных лекций А. А. Зализняка. Данные собраны в проекте
  <a href="https://github.com/gasyoun/BookIndex">BookIndex</a>;
  полная корпусная оболочка (указатель, KWIC, симуляторы) —
  <a href="{esc(BOOKINDEX_VIDEO)}">видеогалерея BookIndex</a>.</p>
  <p>Видео размещены на YouTube правообладателями/архивами; здесь — только индекс и ссылки.
  Сборка: {esc(BUILT_AT)} ·
  <a href="https://github.com/gasyoun/ZalizniakVideo">исходники</a></p>
</footer>
"""


def render_index(videos: list[dict], meta: dict) -> str:
    themes = sorted({v.get("theme") for v in videos if v.get("theme")})
    theme_opts = ['<option value="">Все темы</option>'] + [
        f'<option value="{esc(t)}">{esc(t)}</option>' for t in themes
    ]
    hours = sum(int(v.get("duration") or 0) for v in videos) / 3600.0
    n_coll = len(meta.get("collisions") or [])

    cards = []
    for v in videos:
        search = " ".join(
            [
                v.get("title") or "",
                " ".join(v.get("titles_all") or []),
                v.get("theme") or "",
                v.get("id") or "",
            ]
        ).lower()
        chips = []
        if v.get("theme"):
            chips.append(f'<span class="chip">{esc(v["theme"])}</span>')
        if v.get("collision"):
            chips.append(
                f'<span class="chip warn" title="Несколько разных заголовков на один YouTube id">'
                f"коллизия ×{len(v['titles_all'])}</span>"
            )
        if v.get("stage"):
            chips.append(f'<span class="chip">{esc(v["stage"])}</span>')
        cards.append(
            f"""
<li class="card" data-card
    data-search="{esc(search)}"
    data-theme="{esc(v.get('theme') or '')}"
    data-title="{esc(v.get('title') or '')}"
    data-date="{esc(v.get('date') or '')}"
    data-duration="{int(v.get('duration') or 0)}">
  <a class="title" href="{esc(v['path'])}">{esc(v.get('title') or v['id'])}</a>
  <div class="row">
    <span>{esc(fmt_duration(v.get('duration')))}</span>
    <span>{esc(v.get('date') or 'дата не указана')}</span>
    <span>id: {esc(v['id'])}</span>
  </div>
  <div class="row">{''.join(chips)}</div>
</li>"""
        )

    body = f"""
<header class="site">
  <div class="wrap">
    <div class="brand">ZalizniakVideo · только видео</div>
    <h1>Публичные лекции А. А. Зализняка</h1>
    <p class="lede">Индекс записей на YouTube: отдельная страница на каждое видео.
    Это не расшифровки и не главы книги «Из жизни слов и языков» — только каталог выступлений.</p>
    <div class="meta-bar">
      <span><strong>{len(videos)}</strong> видео</span>
      <span><strong>{hours:.0f}</strong> ч суммарно</span>
      <span>исходный каталог: <strong>{meta['raw_catalog_rows']}</strong> строк →
        <strong>{meta['unique_videos']}</strong> уникальных id</span>
      <span>коллизии id: <strong>{n_coll}</strong></span>
    </div>
  </div>
</header>
<main class="wrap">
  <div class="controls">
    <div>
      <label for="q">Поиск</label>
      <input id="q" type="search" placeholder="название, тема, id…" autocomplete="off">
    </div>
    <div>
      <label for="theme">Тема (конвейер)</label>
      <select id="theme">{''.join(theme_opts)}</select>
    </div>
    <div>
      <label for="sort">Сортировка</label>
      <select id="sort">
        <option value="title" selected>по названию</option>
        <option value="duration-desc">дольше сначала</option>
        <option value="duration-asc">короче сначала</option>
        <option value="date-desc">новее (где есть дата)</option>
        <option value="date-asc">старше (где есть дата)</option>
      </select>
    </div>
  </div>
  <p id="result-count" role="status" aria-live="polite"></p>
  <ul class="list" id="video-list">
    {''.join(cards)}
  </ul>
  <div id="empty" class="empty">Ничего не найдено. Сбросьте поиск или тему.</div>
  <p class="note">Прямая ссылка на этот индекс:
    <a href="{esc(SITE_BASE)}/">{esc(SITE_BASE)}/</a>.
    Корпусная галерея в BookIndex:
    <a href="{esc(BOOKINDEX_VIDEO)}">{esc(BOOKINDEX_VIDEO)}</a>.</p>
</main>
{footer_html()}
"""
    scripts = f"<script>{INDEX_JS}</script>"
    return page_shell(
        title="Видеолекции А. А. Зализняка — каталог",
        description=(
            f"Индекс {len(videos)} публичных видеолекций академика А. А. Зализняка "
            f"(~{hours:.0f} ч). Отдельная страница на каждое видео."
        ),
        canonical=f"{SITE_BASE}/",
        body=body,
        scripts=scripts,
    )


def render_video(v: dict) -> str:
    rid = v["id"]
    title = v.get("title") or rid
    desc = f"Видеолекция: {title}. А. А. Зализняк."
    yt = v.get("url") or f"https://www.youtube.com/watch?v={rid}"
    embed = f"https://www.youtube-nocookie.com/embed/{rid}"
    entities = v.get("related_entities") or []
    # Cap chips for readability
    ent_html = []
    for e in entities[:40]:
        head = e.get("head") or ""
        if not head:
            continue
        t = e.get("t")
        t_html = f'<span class="t">▸ {int(t)//60}:{int(t)%60:02d}</span>' if t is not None else ""
        ent_html.append(f'<span class="entity">{esc(head)}{t_html}</span>')

    collision_block = ""
    if v.get("collision"):
        lis = "".join(f"<li>{esc(t)}</li>" for t in v.get("titles_all") or [])
        collision_block = f"""
<div class="section">
  <h2>⚠ Несколько заголовков на один YouTube id</h2>
  <p class="note">В исходном каталоге BookIndex на id <code>{esc(rid)}</code>
  висят разные названия семинаров. На YouTube это одна запись; лишние названия —
  ошибка сопоставления (см. issue в репозитории). Сохранены все варианты:</p>
  <ul>{lis}</ul>
</div>
"""

    meta_bits = [
        f"<span>Длительность: <strong>{esc(fmt_duration(v.get('duration')))}</strong></span>",
        f"<span>Дата: <strong>{esc(v.get('date') or 'не указана')}</strong></span>",
    ]
    if v.get("theme"):
        meta_bits.append(f"<span>Тема: <strong>{esc(v['theme'])}</strong></span>")
    if v.get("stage"):
        meta_bits.append(f"<span>Стадия конвейера: <strong>{esc(v['stage'])}</strong></span>")

    body = f"""
<header class="site">
  <div class="wrap">
    <p class="crumbs"><a href="../../">← Все видео</a></p>
    <div class="brand">ZalizniakVideo</div>
    <h1>{esc(title)}</h1>
    <div class="meta-bar">{''.join(meta_bits)}</div>
  </div>
</header>
<main class="wrap">
  <div class="player">
    <iframe
      src="{esc(embed)}"
      title="{esc(title)}"
      allow="accelerometer; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
      allowfullscreen
      loading="lazy"
      referrerpolicy="strict-origin-when-cross-origin"></iframe>
  </div>
  <div class="actions">
    <a class="btn primary" href="{esc(yt)}" rel="noopener noreferrer" target="_blank">Открыть на YouTube</a>
    <a class="btn" href="{esc(BOOKINDEX_VIDEO_DETAIL.format(id=rid))}" rel="noopener noreferrer">Карточка в BookIndex</a>
    <a class="btn" href="../../">К каталогу</a>
  </div>
  {collision_block}
  <div class="section">
    <h2>Связанные сущности</h2>
    {('<div class="entities">' + ''.join(ent_html) + '</div>') if ent_html else '<p class="note">Пока нет разметки сущностей для этого ролика.</p>'}
    <p class="note">Метки минут (▸ ММ:СС), если есть, ведут к моменту в расшифровке/KWIC в BookIndex; полный текст расшифровки здесь не публикуется.</p>
  </div>
  <p class="note">Постоянная ссылка на эту страницу:
    <a href="{esc(SITE_BASE)}/video/{esc(rid)}/">{esc(SITE_BASE)}/video/{esc(rid)}/</a></p>
</main>
{footer_html()}
"""
    return page_shell(
        title=f"{title} — Зализняк",
        description=desc,
        canonical=f"{SITE_BASE}/video/{rid}/",
        body=body,
    )


def write_sitemap(videos: list[dict]) -> str:
    urls = [f"  <url><loc>{SITE_BASE}/</loc><changefreq>weekly</changefreq></url>"]
    for v in videos:
        urls.append(
            f"  <url><loc>{SITE_BASE}/video/{v['id']}/</loc>"
            f"<changefreq>monthly</changefreq></url>"
        )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(urls)
        + "\n</urlset>\n"
    )


def main() -> int:
    app_data = BOOKINDEX / "app_data.json"
    pipeline_path = BOOKINDEX / "data" / "video_pipeline.json"
    if not app_data.is_file():
        print(f"ERROR: missing {app_data}", file=sys.stderr)
        return 1
    if not pipeline_path.is_file():
        print(f"ERROR: missing {pipeline_path}", file=sys.stderr)
        return 1

    catalog = load_json(app_data).get("video_catalog") or []
    pipeline = load_json(pipeline_path)
    videos, meta = merge_catalog(catalog, pipeline)

    data_dir = ROOT / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    # JSON export (stable public API for other consumers)
    export = {
        "schema": "zalizniak-video-catalog/1",
        "site": SITE_BASE,
        "built_at": BUILT_AT,
        "stats": {
            "unique_videos": len(videos),
            "raw_catalog_rows": meta["raw_catalog_rows"],
            "pipeline_videos": meta["pipeline_videos"],
            "total_hours": round(sum(int(v.get("duration") or 0) for v in videos) / 3600.0, 2),
            "collisions": len(meta["collisions"]),
        },
        "collisions": meta["collisions"],
        "videos": [
            {
                "id": v["id"],
                "title": v["title"],
                "url": v["url"],
                "path": v["path"],
                "date": v.get("date"),
                "duration": v.get("duration"),
                "theme": v.get("theme"),
                "stage": v.get("stage"),
                "collision": v.get("collision"),
                "titles_all": v.get("titles_all"),
                "related_entities": v.get("related_entities") or [],
            }
            for v in videos
        ],
    }
    (data_dir / "catalog.json").write_text(
        json.dumps(export, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (data_dir / "stats.json").write_text(
        json.dumps(export["stats"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    (ROOT / "index.html").write_text(render_index(videos, meta), encoding="utf-8")
    (ROOT / "sitemap.xml").write_text(write_sitemap(videos), encoding="utf-8")
    (ROOT / ".nojekyll").write_text("", encoding="utf-8")
    (ROOT / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\nSitemap: {SITE_BASE}/sitemap.xml\n",
        encoding="utf-8",
    )

    # Wipe old video pages that no longer exist? keep simple: rewrite all known
    video_root = ROOT / "video"
    video_root.mkdir(exist_ok=True)
    for v in videos:
        d = video_root / v["id"]
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(render_video(v), encoding="utf-8")

    print(
        f"OK: {len(videos)} video pages · "
        f"collisions={len(meta['collisions'])} · "
        f"out={ROOT}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
