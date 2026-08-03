#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build the static ZalizniakVideo scholarly gallery.

The preferred input is BookIndex ``data/video_catalog_public.json``.  Until
that export is available, the checked-in v1 catalog is accepted as a migration
fixture.  The normal build is offline and requires every local thumbnail.
Pass ``--fetch-thumbnails`` explicitly to refresh the cache from YouTube.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import shutil
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Iterable

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PUBLIC_CATALOG = ROOT.parent / "BookIndex" / "data" / "video_catalog_public.v2.json"
LEGACY_PUBLIC_CATALOG = ROOT.parent / "BookIndex" / "data" / "video_catalog_public.json"
FALLBACK_CATALOG = ROOT / "data" / "catalog.json"
SITE_BASE = os.environ.get(
    "SITE_BASE", "https://gasyoun.github.io/ZalizniakVideo"
).rstrip("/")
BOOKINDEX_VIDEO = "https://gasyoun.github.io/BookIndex/aaz-index.html#v4/materials/video"


CSS = r"""
:root {
  color-scheme: light dark;
  --paper: #f4efe5;
  --surface: #fbf8f1;
  --surface-strong: #fffdf8;
  --ink: #24211d;
  --muted: #676057;
  --line: #cfc6b8;
  --accent: #7a2f2b;
  --accent-strong: #5f211e;
  --action: #712621;
  --focus: #7a2f2b;
  --player: #171512;
  --radius-sm: .25rem;
  --radius-md: .5rem;
  --radius-lg: .75rem;
  --max: 88rem;
  --serif: Georgia, "Times New Roman", serif;
  --sans: "Segoe UI", Arial, sans-serif;
}
@media (prefers-color-scheme: dark) {
  :root {
    --paper: #181715;
    --surface: #211f1c;
    --surface-strong: #292622;
    --ink: #f1ece2;
    --muted: #bbb2a5;
    --line: #4a443c;
    --accent: #d58a82;
    --accent-strong: #efaaa2;
    --action: #934640;
    --focus: #efaaa2;
    --player: #0b0a09;
  }
}
* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
  margin: 0;
  background: var(--paper);
  color: var(--ink);
  font-family: var(--sans);
  line-height: 1.55;
}
a { color: var(--accent-strong); text-underline-offset: .18em; }
a:hover { text-decoration-thickness: .12em; }
a:focus-visible, button:focus-visible, input:focus-visible, select:focus-visible {
  outline: .18rem solid var(--focus);
  outline-offset: .16rem;
}
.skip-link {
  position: fixed; left: .75rem; top: .75rem; z-index: 20;
  transform: translateY(-180%); padding: .7rem 1rem;
  background: var(--surface-strong); color: var(--ink); border: 1px solid var(--line);
}
.skip-link:focus { transform: translateY(0); }
.wrap { width: min(calc(100% - 2rem), var(--max)); margin-inline: auto; }
.masthead { border-bottom: 1px solid var(--line); padding: 1.2rem 0 1.4rem; }
.brand-row { display: flex; align-items: baseline; justify-content: space-between; gap: 1rem; }
.brand { font: 600 .78rem/1 var(--sans); letter-spacing: .13em; text-transform: uppercase; color: var(--muted); }
.accession { font-variant-numeric: tabular-nums; letter-spacing: .08em; color: var(--muted); }
h1, h2 { font-family: var(--serif); font-weight: 600; letter-spacing: -.018em; text-wrap: balance; }
h1 { max-width: 25ch; margin: .45rem 0 .35rem; font-size: clamp(1.7rem, 4vw, 3rem); line-height: 1.08; }
h2 { margin: 0 0 .6rem; font-size: clamp(1.25rem, 2vw, 1.65rem); line-height: 1.2; }
.lede { max-width: 66ch; margin: 0; color: var(--muted); text-wrap: pretty; }
.archive-facts { display: flex; flex-wrap: wrap; gap: .35rem 1.1rem; margin-top: .8rem; color: var(--muted); font-size: .9rem; }
.archive-facts strong { color: var(--ink); font-variant-numeric: tabular-nums; }
main { padding-block: 1.25rem 3rem; }
.filters {
  display: grid; grid-template-columns: minmax(13rem, 2fr) repeat(5, minmax(8rem, 1fr)); gap: .65rem;
  padding: .8rem; margin-bottom: .7rem; border: 1px solid var(--line);
  border-radius: var(--radius-lg); background: var(--surface);
}
.field { min-width: 0; }
.field label { display: block; margin-bottom: .18rem; color: var(--muted); font-size: .76rem; font-weight: 600; }
input, select, button { font: inherit; }
input[type="search"], select {
  width: 100%; max-width: 100%; min-width: 0; min-height: 2.75rem; padding: .55rem .65rem;
  color: var(--ink); background: var(--surface-strong); border: 1px solid var(--line); border-radius: var(--radius-sm);
}
.filter-actions { display: flex; align-items: end; }
.reset, .button {
  min-height: 2.75rem; border: 1px solid var(--line); border-radius: var(--radius-sm);
  padding: .55rem .8rem; background: var(--surface-strong); color: var(--ink); cursor: pointer;
}
.reset:hover, .button:hover { border-color: var(--accent); color: var(--accent-strong); }
.results { min-height: 1.5rem; margin: .55rem 0 .75rem; color: var(--muted); font-size: .9rem; }
.gallery { list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 1rem; }
.card { min-width: 0; background: var(--surface); border-bottom: 1px solid var(--line); padding-bottom: 1rem; }
.card-link { display: block; color: inherit; text-decoration: none; }
.thumb { display: block; width: 100%; aspect-ratio: 16/9; object-fit: cover; background: var(--player); border-radius: var(--radius-md); }
.card-link:hover .thumb { outline: 2px solid var(--accent); outline-offset: 2px; }
.card-kicker { display: flex; justify-content: space-between; gap: .7rem; margin-top: .55rem; font-size: .75rem; color: var(--muted); }
.card h2 { margin: .25rem 0 .3rem; font-size: 1.12rem; line-height: 1.25; overflow-wrap: anywhere; }
.card-meta, .card-tags, .contributors { margin: .18rem 0 0; color: var(--muted); font-size: .82rem; }
.card-tags { color: var(--ink); }
.empty { display: none; padding: 2rem 1rem; border: 1px dashed var(--line); border-radius: var(--radius-md); text-align: center; color: var(--muted); }
.empty.show { display: block; }
.hidden { display: none !important; }
.breadcrumbs { margin: 0 0 .6rem; font-size: .86rem; color: var(--muted); }
.detail-grid { display: grid; grid-template-columns: minmax(0, 2fr) minmax(16rem, .85fr); gap: 2rem; align-items: start; }
.player-shell { position: relative; width: 100%; aspect-ratio: 16/9; overflow: hidden; border-radius: var(--radius-lg); background: var(--player); }
.player-button { position: absolute; inset: 0; width: 100%; height: 100%; padding: 0; border: 0; cursor: pointer; background: var(--player); color: white; }
.player-button img { display: block; width: 100%; height: 100%; object-fit: cover; opacity: .75; }
.play-label { position: absolute; inset: 50% auto auto 50%; transform: translate(-50%, -50%); min-height: 2.75rem; display: inline-flex; align-items: center; padding: .65rem 1rem; border-radius: var(--radius-sm); background: rgba(20,18,15,.9); color: #fff; font-weight: 600; }
.player-shell iframe { position: absolute; inset: 0; width: 100%; height: 100%; border: 0; }
.watch-fallback { margin: .55rem 0 0; font-size: .86rem; }
.detail-actions { display: flex; flex-wrap: wrap; gap: .55rem; margin: 1rem 0 1.6rem; }
.button { display: inline-flex; align-items: center; text-decoration: none; }
.button.primary { border-color: var(--action); background: var(--action); color: #fff; }
.button.primary:hover { filter: brightness(.9); color: #fff; }
.section { margin-top: 1.7rem; }
.facts { margin: 0; }
.facts div { display: grid; grid-template-columns: minmax(7rem, .7fr) 1.5fr; gap: .7rem; padding: .55rem 0; border-bottom: 1px solid var(--line); }
.facts dt { color: var(--muted); }
.facts dd { margin: 0; overflow-wrap: anywhere; }
.entity-list { display: flex; flex-wrap: wrap; gap: .4rem; padding: 0; list-style: none; }
.entity-list li { padding: .3rem .5rem; border: 1px solid var(--line); border-radius: var(--radius-sm); background: var(--surface); font-size: .83rem; }
.note { max-width: 70ch; color: var(--muted); font-size: .88rem; }
.citation { padding: .85rem; border-left: .2rem solid var(--accent); background: var(--surface); overflow-wrap: anywhere; }
.site-footer { border-top: 1px solid var(--line); padding: 1.25rem 0 2.5rem; color: var(--muted); font-size: .82rem; }
.site-footer p { max-width: 78ch; }
@media (max-width: 72rem) { .filters { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
@media (max-width: 54rem) { .gallery { grid-template-columns: repeat(2, minmax(0, 1fr)); } .detail-grid { grid-template-columns: 1fr; } }
@media (max-width: 38rem) {
  .wrap { width: min(calc(100% - 1.25rem), var(--max)); }
  .filters { grid-template-columns: 1fr; }
  .gallery { grid-template-columns: 1fr; }
  .brand-row { align-items: flex-start; flex-direction: column; gap: .35rem; }
  .facts div { grid-template-columns: 1fr; gap: .1rem; }
  .detail-actions .button { width: 100%; justify-content: center; }
}
@media (prefers-reduced-motion: reduce) { html { scroll-behavior: auto; } }
"""


INDEX_JS = r"""
(function () {
  const cards = Array.from(document.querySelectorAll('[data-card]'));
  const controls = Array.from(document.querySelectorAll('[data-filter]'));
  const count = document.getElementById('result-count');
  const empty = document.getElementById('empty');
  const reset = document.getElementById('reset');
  const norm = value => (value || '').toLocaleLowerCase('ru').replace(/ё/g, 'е');

  function readUrl() {
    const params = new URLSearchParams(location.search);
    controls.forEach(el => { el.value = params.get(el.name) || ''; });
  }
  function writeUrl() {
    const params = new URLSearchParams();
    controls.forEach(el => { if (el.value) params.set(el.name, el.value); });
    const query = params.toString();
    history.replaceState(null, '', location.pathname + (query ? '?' + query : '') + location.hash);
  }
  function apply(updateUrl) {
    const values = Object.fromEntries(controls.map(el => [el.name, norm(el.value.trim())]));
    let shown = 0;
    cards.forEach(card => {
      const searchOk = !values.q || norm(card.dataset.search).includes(values.q);
      const filterOk = ['topic', 'type', 'series', 'year', 'transcript'].every(key => {
        if (!values[key]) return true;
        return norm(card.dataset[key]).split('|').includes(values[key]);
      });
      const visible = searchOk && filterOk;
      card.classList.toggle('hidden', !visible);
      if (visible) shown += 1;
    });
    count.textContent = 'Показано записей: ' + shown + ' из ' + cards.length;
    empty.classList.toggle('show', shown === 0);
    if (updateUrl) writeUrl();
  }
  controls.forEach(el => el.addEventListener(el.type === 'search' ? 'input' : 'change', () => apply(true)));
  reset.addEventListener('click', () => { controls.forEach(el => { el.value = ''; }); apply(true); controls[0].focus(); });
  addEventListener('popstate', () => { readUrl(); apply(false); });
  readUrl();
  apply(false);
})();
"""


PLAYER_JS = r"""
(function () {
  const button = document.querySelector('[data-load-player]');
  if (!button) return;
  button.addEventListener('click', function () {
    const frame = document.createElement('iframe');
    frame.src = button.dataset.embed;
    frame.title = button.dataset.title;
    frame.allow = 'accelerometer; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share';
    frame.allowFullscreen = true;
    frame.referrerPolicy = 'strict-origin-when-cross-origin';
    button.replaceWith(frame);
    frame.tabIndex = -1;
    frame.focus();
  });
  document.querySelectorAll('[data-copy]').forEach(function (copy) {
    copy.addEventListener('click', async function () {
      const value = document.getElementById(copy.dataset.copy).textContent.trim();
      try { await navigator.clipboard.writeText(value); copy.textContent = 'Скопировано'; document.getElementById('copy-status').textContent = 'Текст скопирован'; }
      catch (_) { window.prompt('Скопируйте текст', value); }
    });
  });
})();
"""


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def visible(value: Any) -> str:
    """Normalize visible punctuation while leaving JSON source values intact."""
    return str(value or "").replace("\u2013", "-").replace("\u2014", "-")


def youtube_id(value: Any) -> str | None:
    text = str(value or "")
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", text):
        return text
    match = re.search(r"(?:v=|youtu\.be/|embed/|shorts/)([A-Za-z0-9_-]{11})", text)
    return match.group(1) if match else None


def first(record: dict, *keys: str, default: Any = None) -> Any:
    for key in keys:
        if record.get(key) not in (None, ""):
            return record[key]
    return default


def list_value(value: Any) -> list:
    if value in (None, ""):
        return []
    return value if isinstance(value, list) else [value]


def parse_duration(value: Any) -> int:
    if isinstance(value, (int, float)):
        return max(0, int(value))
    text = str(value or "")
    if text.isdigit():
        return int(text)
    iso = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", text)
    if iso:
        return int(iso.group(1) or 0) * 3600 + int(iso.group(2) or 0) * 60 + int(iso.group(3) or 0)
    return 0


def iso_duration(seconds: int) -> str:
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    return "PT" + (f"{hours}H" if hours else "") + (f"{minutes}M" if minutes else "") + f"{secs}S"


def fmt_duration(value: Any) -> str:
    seconds = parse_duration(value)
    if not seconds:
        return "не указана"
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def display_date(record: dict) -> str:
    value = record.get("date_recorded") or record.get("upload_date")
    return visible(value) if value else "дата неизвестна"


def option_values(records: Iterable[dict], key: str) -> list[str]:
    values = set()
    for record in records:
        for value in list_value(record.get(key)):
            if value:
                values.add(str(value))
    return sorted(values, key=str.casefold)


def contributor_names(value: Any) -> list[str]:
    role_labels = {
        "speaker": "выступающий",
        "lecturer": "лектор",
        "interviewer": "интервьюер",
        "moderator": "модератор",
        "participant": "участник",
        "host": "ведущий",
    }
    names = []
    for contributor in list_value(value):
        if isinstance(contributor, dict):
            name = first(contributor, "name", "label", "title")
            role = contributor.get("role")
            if name:
                role_label = role_labels.get(str(role), str(role)) if role else None
                names.append(f"{name}, {role_label}" if role_label else str(name))
        elif contributor:
            names.append(str(contributor))
    return names


def evidence_data(record: dict) -> list[Any]:
    """Normalize the public v2 evidence block while accepting v1 provenance."""
    evidence = first(record, "evidence", "provenance", "sources")
    if isinstance(evidence, dict):
        evidence = first(evidence, "items", "records", "sources", default=[evidence])
    normalized = []
    preferred = ("url", "label", "accessed_at", "supports")
    for item in list_value(evidence):
        if not isinstance(item, dict):
            normalized.append(item)
            continue
        keys = [key for key in preferred if key in item]
        keys.extend(sorted(key for key in item if key not in preferred))
        normalized.append({key: item[key] for key in keys})
    return normalized


def transcript_data(record: dict) -> dict:
    raw = record.get("transcript")
    if isinstance(raw, dict):
        status = first(raw, "status", "state", default="none")
        url = first(raw, "url", "href")
        verified = bool(raw.get("verified") or str(status).casefold() in {"verified", "проверена", "complete", "checked", "edited", "published"})
    else:
        status = first(record, "transcript_status", "stage", default="none")
        url = first(record, "transcript_url")
        verified = bool(
            record.get("transcript_verified")
            or str(status).casefold() in {"verified", "проверена", "complete", "checked", "edited", "published"}
        )
    normalized = str(status or "none").casefold()
    controlled = {
        "unknown": ("none", "статус неизвестен"),
        "none": ("none", "нет"),
        "automatic": ("indexed", "автоматическая"),
        "partial": ("indexed", "частичная"),
        "checked": ("verified", "проверена"),
        "edited": ("verified", "отредактирована"),
        "published": ("verified", "опубликована"),
        "problem": ("indexed", "требует проверки"),
    }
    if normalized in controlled:
        bucket, label = controlled[normalized]
    elif verified and url:
        bucket, label = "verified", "проверена"
    elif normalized not in {"", "missing", "absent", "нет"}:
        bucket, label = "indexed", "есть сведения"
    else:
        bucket, label = "none", "нет сведений"
    return {"status": str(status or "none"), "bucket": bucket, "label": label, "url": url, "verified": bool(verified and url)}


def infer_type(title: str) -> str:
    lowered = title.casefold()
    if any(word in lowered for word in ("интервью", "беседа")):
        return "интервью"
    if any(word in lowered for word in ("фильм", "документаль")):
        return "фильм"
    if any(word in lowered for word in ("семинар", "конференц")):
        return "семинар"
    return "лекция"


def normalize_records(payload: Any) -> tuple[list[dict], dict]:
    if isinstance(payload, list):
        raw_records, meta = payload, {}
    elif isinstance(payload, dict):
        raw_records = next((payload.get(k) for k in ("records", "videos", "items", "catalog") if isinstance(payload.get(k), list)), [])
        meta = payload
    else:
        raise ValueError("catalog root must be an object or array")

    prepared = []
    for raw in raw_records:
        if not isinstance(raw, dict):
            continue
        source = raw.get("source") if isinstance(raw.get("source"), dict) else {}
        rid = youtube_id(first(raw, "youtube_id", "id", "url", "youtube_url") or first(source, "youtube_id", "url"))
        if not rid:
            continue
        title = str(first(raw, "title_display", "human_title", "title", "display_title", default=rid)).strip()
        accession_raw = first(raw, "accession", "record_accession", "catalog_number")
        accession = str(accession_raw).zfill(3) if str(accession_raw or "").isdigit() else None
        duration = parse_duration(first(raw, "duration", "duration_seconds", "duration_sec"))
        date_recorded = first(raw, "date_recorded", "recorded_date")
        upload_date = first(raw, "upload_date", "date_uploaded", "date")
        topics = [str(value) for value in list_value(first(raw, "topics", "topic", "theme")) if value]
        topic = topics[0] if topics else None
        kind = first(raw, "type", "record_type", "genre")
        series = first(raw, "purpose", "series", "collection")
        transcript = transcript_data(raw)
        url = first(raw, "watch_url", "url", "youtube_url", default=f"https://www.youtube.com/watch?v={rid}")
        contributors_raw = first(raw, "contributors", "creators", "participants")
        prepared.append({
            "_source": raw,
            "accession": accession,
            "id": rid,
            "title": title,
            "title_source": first(raw, "title_source", default=title),
            "url": url,
            "date": first(raw, "date", default=upload_date),
            "date_recorded": date_recorded,
            "upload_date": upload_date,
            "year": str(first(raw, "year", default=(str(date_recorded or upload_date)[:4] if date_recorded or upload_date else ""))),
            "duration": duration,
            "topic": topic,
            "topics": topics,
            "type": kind,
            "series": series,
            "purpose": raw.get("purpose"),
            "last_verified_at": raw.get("last_verified_at"),
            "contributors": list_value(contributors_raw),
            "contributor_labels": contributor_names(contributors_raw),
            "transcript": transcript,
            "bibliography": list_value(first(raw, "bibliography", "citations")),
            "provenance": evidence_data(raw),
            "evidence": evidence_data(raw),
            "related_entities": list_value(raw.get("related_entities")),
            "description": first(raw, "description", "abstract"),
            "stage": raw.get("stage"),
            "collision": bool(raw.get("collision")),
            "titles_all": list_value(raw.get("titles_all")) or [title],
        })

    # Fallback accessions exist only to make the migration fixture buildable.
    # The public BookIndex export supplies frozen accessions and wins here.
    ordered = sorted(prepared, key=lambda r: (r["title"].casefold(), r["id"]))
    used: set[str] = set()
    for number, record in enumerate(ordered, 1):
        accession = record["accession"] or f"{number:03d}"
        if not re.fullmatch(r"\d{3}", accession):
            raise ValueError(f"invalid accession {accession!r} for {record['id']}")
        if accession in used:
            raise ValueError(f"duplicate accession {accession}")
        used.add(accession)
        record["accession"] = accession
        record["path"] = f"v/{accession}/"
        record["legacy_path"] = f"video/{record['id']}/"
    return sorted(ordered, key=lambda r: r["accession"]), meta


def page_shell(*, title: str, description: str, canonical: str, body: str, og_type: str = "website", og_image: str | None = None, json_ld: dict | None = None, robots: str = "index, follow", scripts: str = "", extra_head: str = "") -> str:
    social_image = f'<meta property="og:image" content="{esc(og_image)}">\n<meta name="twitter:image" content="{esc(og_image)}">' if og_image else ""
    structured = f'<script type="application/ld+json">{json.dumps(json_ld, ensure_ascii=False, separators=(",", ":"), sort_keys=True).replace("</", "<\\/")}</script>' if json_ld else ""
    return f'''<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(visible(title))}</title>
<meta name="description" content="{esc(visible(description))}">
<meta name="robots" content="{esc(robots)}">
<link rel="canonical" href="{esc(canonical)}">
<meta property="og:type" content="{esc(og_type)}">
<meta property="og:title" content="{esc(visible(title))}">
<meta property="og:description" content="{esc(visible(description))}">
<meta property="og:url" content="{esc(canonical)}">
<meta name="twitter:card" content="summary_large_image">
{social_image}
<meta name="theme-color" content="#7a2f2b">
<style>{CSS}</style>
{structured}
{extra_head}
</head>
<body>
<a class="skip-link" href="#main">К основному содержанию</a>
{body}
{scripts}
</body>
</html>
'''


def footer_html() -> str:
    return f'''<footer class="site-footer"><div class="wrap">
<p>Научно-редакционный указатель публичных видеозаписей. Видео хранятся у их правообладателей. Каталог связывает записи, проверяемые метаданные и материалы <a href="{esc(BOOKINDEX_VIDEO)}">BookIndex</a>.</p>
<p><a href="data/catalog.json">JSON v1</a> · <a href="data/catalog.v2.json">JSON v2</a> · <a href="https://github.com/gasyoun/ZalizniakVideo">Исходный код</a></p>
</div></footer>'''


def filter_select(name: str, label: str, values: list[str], all_label: str) -> str:
    options = [f'<option value="">{esc(all_label)}</option>'] + [f'<option value="{esc(v)}">{esc(visible(v))}</option>' for v in values]
    return f'<div class="field"><label for="{name}">{esc(label)}</label><select id="{name}" name="{name}" data-filter>{"".join(options)}</select></div>'


def render_index(records: list[dict]) -> str:
    cards = []
    for record in records:
        date = display_date(record)
        tags = " · ".join(visible(v) for v in ([record.get("type") or "тип не указан"] + record.get("topics", [])) if v)
        contributors = ", ".join(visible(v) for v in record["contributor_labels"])
        search = " ".join(str(v or "") for v in (record["accession"], record["id"], record["title"], contributors, record.get("topic"), record.get("series")))
        cards.append(f'''<li class="card" data-card data-search="{esc(search)}" data-topic="{esc('|'.join(record.get('topics', [])))}" data-type="{esc(record.get('type') or '')}" data-series="{esc(record.get('series') or '')}" data-year="{esc(record.get('year') or '')}" data-transcript="{esc(record['transcript']['bucket'])}">
<a class="card-link" href="{esc(record['path'])}">
<img class="thumb" src="assets/thumbs/{record['accession']}.jpg" alt="" width="480" height="270" loading="lazy" decoding="async">
<div class="card-kicker"><span class="accession">№ {record['accession']}</span><span>{esc(fmt_duration(record['duration']))}</span></div>
<h2>{esc(visible(record['title']))}</h2>
</a>
{f'<p class="contributors">{esc(contributors)}</p>' if contributors else ''}
<p class="card-meta">{esc(visible(date))} · Расшифровка: {esc(record['transcript']['label'])}</p>
{f'<p class="card-tags">{esc(tags)}</p>' if tags else ''}
</li>''')
    filters = [
        '<div class="field"><label for="q">Поиск по архиву</label><input id="q" name="q" data-filter type="search" autocomplete="off" placeholder="Название, участник, номер"></div>',
        filter_select("topic", "Тема", option_values(records, "topics"), "Все темы"),
        filter_select("type", "Тип", option_values(records, "type"), "Все типы"),
        filter_select("series", "Серия", option_values(records, "series"), "Все серии"),
        filter_select("year", "Год", option_values(records, "year"), "Все годы"),
        filter_select("transcript", "Расшифровка", ["verified", "indexed", "none"], "Любой статус"),
        '<div class="filter-actions"><button class="reset" id="reset" type="button">Сбросить</button></div>',
    ]
    body = f'''<header class="masthead"><div class="wrap">
<div class="brand-row"><div class="brand">ZalizniakVideo · Архив видеозаписей</div><div class="accession">Редакционный каталог</div></div>
<h1>А. А. Зализняк: видеозаписи и материалы</h1>
<p class="lede">Публичный научно-редакционный архив для читателей, исследователей и студентов. Каждая запись имеет постоянный номер, библиографию и сведения о происхождении, когда они подтверждены источником.</p>
<div class="archive-facts"><span><strong>{len(records)}</strong> записей</span><span>Постоянная нумерация</span><span>Локальные обложки</span></div>
</div></header>
<main class="wrap" id="main">
<form class="filters" role="search" onsubmit="return false">{"".join(filters)}</form>
<p class="results" id="result-count" role="status" aria-live="polite">Всего записей: {len(records)}</p>
<ul class="gallery">{"".join(cards)}</ul>
<div class="empty" id="empty"><strong>Записей с такими параметрами нет.</strong><br>Измените запрос или сбросьте фильтры.</div>
</main>{footer_html()}'''
    description = f"Научно-редакционный архив из {len(records)} публичных видеозаписей, связанных с работами А. А. Зализняка."
    return page_shell(title="А. А. Зализняк: архив видеозаписей", description=description, canonical=f"{SITE_BASE}/", body=body, scripts=f"<script>{INDEX_JS}</script>")


def render_list(values: list[Any]) -> str:
    items = []
    for value in values:
        if isinstance(value, dict):
            label = first(value, "label", "title", "citation", "source", "name", default=json.dumps(value, ensure_ascii=False, sort_keys=True))
        else:
            label = value
        items.append(f"<li>{esc(visible(label))}</li>")
    return f'<ul>{"".join(items)}</ul>' if items else '<p class="note">Сведения пока не представлены в публичном каталоге.</p>'


def render_evidence(values: list[Any]) -> str:
    """Render compact, link-safe public provenance rather than raw JSON blobs."""
    items = []
    for value in values:
        if not isinstance(value, dict):
            if value:
                items.append(f"<li>{esc(visible(value))}</li>")
            continue
        label = first(value, "label", "title", "citation", "source", "provider", "kind", "name", default="Источник")
        url = first(value, "url", "href", "source_url")
        supports = first(value, "supports", "fields", "claims")
        checked = first(value, "verified_at", "accessed_at", "retrieved_at", "date")
        note = first(value, "note", "description")
        lead = f'<a href="{esc(url)}" rel="noopener noreferrer">{esc(visible(label))}</a>' if url else esc(visible(label))
        details = []
        if supports:
            details.append("подтверждает: " + ", ".join(visible(v) for v in list_value(supports)))
        if checked:
            details.append("проверено " + visible(checked))
        if note:
            details.append(visible(note))
        suffix = f' <span class="note">({esc("; ".join(details))})</span>' if details else ""
        items.append(f"<li>{lead}{suffix}</li>")
    return f'<ul>{"".join(items)}</ul>' if items else '<p class="note">Публичные сведения о происхождении пока не представлены.</p>'


def render_video(record: dict) -> str:
    accession, rid, title = record["accession"], record["id"], record["title"]
    canonical = f"{SITE_BASE}/v/{accession}/"
    image_url = f"{SITE_BASE}/assets/thumbs/{accession}.jpg"
    youtube_url = record["url"]
    embed_url = f"https://www.youtube-nocookie.com/embed/{rid}"
    date = record.get("date_recorded") or record.get("upload_date")
    description = visible(record.get("description") or f"Архивная карточка видеозаписи «{title}»: проверяемые метаданные, происхождение и связанные материалы.")
    citation = f"{visible(title)}. Видеозапись. ZalizniakVideo, № {accession}. {canonical}"
    contributor_value = ", ".join(record["contributor_labels"])
    facts = [
        ("Номер", f"№ {accession}"),
        ("Тип", record.get("type")),
        ("Тема", record.get("topic")),
        ("Серия", record.get("series")),
        ("Дата записи", record.get("date_recorded")),
        ("Дата публикации", record.get("upload_date")),
        ("Длительность", fmt_duration(record.get("duration"))),
        ("Участники", contributor_value),
        ("Последняя проверка", record.get("last_verified_at")),
    ]
    fact_html = "".join(f"<div><dt>{esc(label)}</dt><dd>{esc(visible(value))}</dd></div>" for label, value in facts if value)
    transcript = record["transcript"]
    transcript_html = f'<p><a class="button" href="{esc(transcript["url"])}">Открыть проверенную расшифровку</a></p>' if transcript["verified"] else f'<p class="note">Статус: {esc(transcript["label"])}. Проверенная ссылка на полный текст не опубликована.</p>'
    entities = []
    for entity in record["related_entities"][:48]:
        label = first(entity, "head", "label", "name") if isinstance(entity, dict) else entity
        if label:
            entities.append(f"<li>{esc(visible(label))}</li>")
    json_ld: dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "VideoObject",
        "name": visible(title),
        "description": description,
        "duration": iso_duration(record["duration"]),
        "thumbnailUrl": image_url,
        "embedUrl": embed_url,
        "sameAs": youtube_url,
        "identifier": accession,
        "url": canonical,
    }
    if record.get("date_recorded"):
        json_ld["dateRecorded"] = record["date_recorded"]
    if record.get("upload_date"):
        json_ld["uploadDate"] = record["upload_date"]
    body = f'''<header class="masthead"><div class="wrap">
<p class="breadcrumbs"><a href="../../">Все записи</a> / № {accession}</p>
<div class="brand">ZalizniakVideo · Архивная карточка</div>
<h1>{esc(visible(title))}</h1>
<div class="archive-facts"><span class="accession">№ {accession}</span><span>{esc(display_date(record))}</span><span>{esc(fmt_duration(record['duration']))}</span></div>
</div></header>
<main class="wrap" id="main"><div class="detail-grid"><article>
<div class="player-shell">
<button class="player-button" type="button" data-load-player data-embed="{esc(embed_url)}" data-title="{esc(visible(title))}" aria-label="Загрузить видеоплеер: {esc(visible(title))}">
<img src="../../assets/thumbs/{accession}.jpg" alt="" width="1280" height="720"><span class="play-label">Загрузить видео</span>
</button>
</div>
<p class="watch-fallback">Плеер загружается только по нажатию. <a href="{esc(youtube_url)}" rel="noopener noreferrer">Смотреть на YouTube</a>.</p>
<noscript><p><a class="button primary" href="{esc(youtube_url)}">Смотреть видео на YouTube</a></p></noscript>
<div class="detail-actions"><a class="button primary" href="{esc(youtube_url)}" rel="noopener noreferrer">Открыть на YouTube</a><button class="button" type="button" data-copy="citation">Копировать описание</button><button class="button" type="button" data-copy="permalink">Копировать ссылку</button></div><p class="note" id="copy-status" role="status" aria-live="polite"></p>
<section class="section" aria-labelledby="bibliography"><h2 id="bibliography">Библиография</h2>{render_list(record['bibliography'])}</section>
<section class="section" aria-labelledby="provenance"><h2 id="provenance">Происхождение записи</h2>{render_evidence(record['provenance'])}</section>
<section class="section" aria-labelledby="transcript"><h2 id="transcript">Расшифровка</h2>{transcript_html}</section>
<section class="section" aria-labelledby="entities"><h2 id="entities">Связанные сущности</h2>{f'<ul class="entity-list">{"".join(entities)}</ul>' if entities else '<p class="note">Сущности пока не представлены в публичном каталоге.</p>'}</section>
</article><aside aria-label="Сведения о записи">
<section><h2>Описание записи</h2><dl class="facts">{fact_html}</dl></section>
<section class="section"><h2>Как цитировать</h2><p class="citation" id="citation">{esc(citation)}</p><p class="note">Постоянная ссылка: <span id="permalink">{esc(canonical)}</span></p></section>
</aside></div></main>{footer_html()}'''
    return page_shell(title=f"{title} · Запись № {accession}", description=description, canonical=canonical, body=body, og_type="video.other", og_image=image_url, json_ld=json_ld, scripts=f"<script>{PLAYER_JS}</script>")


def render_alias(record: dict) -> str:
    canonical = f"{SITE_BASE}/v/{record['accession']}/"
    body = f'''<main class="wrap" id="main"><h1>Запись перемещена</h1><p>Постоянная карточка этой записи теперь доступна по адресу <a href="{esc(canonical)}">{esc(canonical)}</a>.</p></main>'''
    return page_shell(title="Запись перемещена", description="Старая ссылка на архивную видеозапись.", canonical=canonical, body=body, robots="noindex, follow", extra_head=f'<meta http-equiv="refresh" content="0; url={esc(canonical)}">')


def v1_export(records: list[dict], source_meta: dict, legacy_meta: dict | None = None) -> dict:
    legacy_meta = legacy_meta or source_meta
    source_videos = legacy_meta.get("videos") if isinstance(legacy_meta, dict) else None
    source_by_id = {str(v.get("id")): v for v in source_videos or [] if isinstance(v, dict)}
    videos = []
    for record in records:
        old = source_by_id.get(record["id"], {})
        videos.append({
            "id": record["id"], "title": old.get("title", record["title"]), "url": old.get("url", record["url"]),
            "path": f"video/{record['id']}/", "date": old.get("date", record.get("date")), "duration": old.get("duration", record["duration"]),
            "theme": old.get("theme", record.get("topic")), "stage": old.get("stage", record.get("stage")), "collision": old.get("collision", record.get("collision", False)),
            "titles_all": old.get("titles_all", record["titles_all"]), "related_entities": old.get("related_entities", record["related_entities"]),
        })
    return {
        "schema": "zalizniak-video-catalog/1", "site": SITE_BASE,
        "built_at": source_meta.get("built_at") or source_meta.get("generated_at") or os.environ.get("BUILD_TIMESTAMP", "source-undated"),
        "stats": {"unique_videos": len(records), "raw_catalog_rows": source_meta.get("stats", {}).get("raw_catalog_rows", source_meta.get("stats", {}).get("source_rows", len(records))), "pipeline_videos": source_meta.get("stats", {}).get("pipeline_videos", source_meta.get("stats", {}).get("videos", len(records))), "total_hours": round(sum(r["duration"] for r in records) / 3600, 2), "collisions": sum(bool(r["collision"]) for r in records)},
        "collisions": source_meta.get("collisions", []), "videos": videos,
    }


def v2_export(records: list[dict], source_meta: dict) -> dict:
    return {
        "schema": "zalizniak-video-catalog/2", "site": SITE_BASE,
        "source_schema": source_meta.get("schema") if isinstance(source_meta, dict) else None,
        "built_at": source_meta.get("generated_at") or source_meta.get("built_at") or os.environ.get("BUILD_TIMESTAMP", "source-undated"),
        "stats": {"records": len(records), "total_hours": round(sum(r["duration"] for r in records) / 3600, 2)},
        "videos": [{k: r.get(k) for k in ("accession", "id", "title_source", "title", "url", "path", "legacy_path", "date_recorded", "upload_date", "year", "duration", "topics", "topic", "type", "purpose", "series", "contributors", "transcript", "bibliography", "provenance", "evidence", "related_entities", "last_verified_at")} for r in records],
    }


def fetch_thumbnails(records: list[dict], thumb_root: Path) -> None:
    thumb_root.mkdir(parents=True, exist_ok=True)
    missing_records = [
        record
        for record in records
        if not (thumb_root / f"{record['accession']}.jpg").is_file()
        or (thumb_root / f"{record['accession']}.jpg").stat().st_size <= 1024
    ]
    if not missing_records:
        print(f"thumbnail cache: all {len(records)} present")
        return

    def fetch_one(record: dict) -> tuple[str, bool]:
        target = thumb_root / f"{record['accession']}.jpg"
        urls = [f"https://i.ytimg.com/vi/{record['id']}/hqdefault.jpg", f"https://i.ytimg.com/vi/{record['id']}/mqdefault.jpg"]
        for url in urls:
            try:
                request = urllib.request.Request(url, headers={"User-Agent": "ZalizniakVideo thumbnail cache/2"})
                with urllib.request.urlopen(request, timeout=20) as response:
                    data = response.read()
                if len(data) > 1024 and data[:2] == b"\xff\xd8":
                    target.write_bytes(data)
                    return record["accession"], True
            except (OSError, urllib.error.URLError):
                continue
        return record["accession"], False

    with ThreadPoolExecutor(max_workers=12) as pool:
        futures = [pool.submit(fetch_one, record) for record in missing_records]
        for index, future in enumerate(as_completed(futures), 1):
            accession, success = future.result()
            print(f"thumbnail {index}/{len(missing_records)}: {accession} {'ok' if success else 'failed'}")


def validate(records: list[dict], thumb_root: Path, allow_missing: bool = False) -> None:
    if not records:
        raise ValueError("catalog has no valid YouTube records")
    if len({r["accession"] for r in records}) != len(records):
        raise ValueError("accessions are not unique")
    if len({r["id"] for r in records}) != len(records):
        raise ValueError("YouTube ids are not unique")
    missing = [r["accession"] for r in records if not (thumb_root / f"{r['accession']}.jpg").is_file()]
    if missing and not allow_missing:
        raise ValueError(f"missing local thumbnails ({len(missing)}): {', '.join(missing[:12])}")


def write_site(records: list[dict], source_meta: dict, root: Path, legacy_meta: dict | None = None) -> None:
    (root / "data").mkdir(parents=True, exist_ok=True)
    (root / "index.html").write_text(render_index(records), encoding="utf-8")
    legacy_export = v1_export(records, source_meta, legacy_meta)
    (root / "data" / "catalog.json").write_text(json.dumps(legacy_export, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (root / "data" / "catalog.v2.json").write_text(json.dumps(v2_export(records, source_meta), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (root / "data" / "stats.json").write_text(json.dumps(legacy_export["stats"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for name in ("v", "video"):
        output = root / name
        if output.exists():
            shutil.rmtree(output)
        output.mkdir()
    for record in records:
        detail = root / record["path"]
        alias = root / record["legacy_path"]
        detail.mkdir(parents=True)
        alias.mkdir(parents=True)
        (detail / "index.html").write_text(render_video(record), encoding="utf-8")
        (alias / "index.html").write_text(render_alias(record), encoding="utf-8")
    urls = [f"  <url><loc>{SITE_BASE}/</loc></url>"] + [f"  <url><loc>{SITE_BASE}/v/{r['accession']}/</loc></url>" for r in records]
    (root / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "\n".join(urls) + "\n</urlset>\n", encoding="utf-8")
    (root / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {SITE_BASE}/sitemap.xml\n", encoding="utf-8")
    (root / ".nojekyll").write_text("", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, help="BookIndex public video catalog")
    parser.add_argument("--output", type=Path, default=ROOT, help="output site root")
    parser.add_argument("--fetch-thumbnails", action="store_true", help="refresh missing thumbnail cache over the network")
    parser.add_argument("--allow-missing-thumbnails", action="store_true", help=argparse.SUPPRESS)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    configured_catalog = os.environ.get("BOOKINDEX_VIDEO_CATALOG")
    input_path = args.catalog or (Path(configured_catalog) if configured_catalog else None)
    input_path = input_path or next((path for path in (DEFAULT_PUBLIC_CATALOG, LEGACY_PUBLIC_CATALOG, FALLBACK_CATALOG) if path.is_file()), FALLBACK_CATALOG)
    if not input_path.is_file():
        print(f"ERROR: missing catalog: {input_path}", file=sys.stderr)
        return 1
    try:
        payload = json.loads(input_path.read_text(encoding="utf-8"))
        legacy_meta = None
        if input_path.resolve() != FALLBACK_CATALOG.resolve() and FALLBACK_CATALOG.is_file():
            candidate = json.loads(FALLBACK_CATALOG.read_text(encoding="utf-8"))
            if candidate.get("schema") == "zalizniak-video-catalog/1":
                legacy_meta = candidate
        records, source_meta = normalize_records(payload)
        thumb_root = args.output / "assets" / "thumbs"
        if args.fetch_thumbnails:
            fetch_thumbnails(records, thumb_root)
        validate(records, thumb_root, args.allow_missing_thumbnails)
        write_site(records, source_meta, args.output, legacy_meta)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"OK: {len(records)} canonical pages, {len(records)} aliases, input={input_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
