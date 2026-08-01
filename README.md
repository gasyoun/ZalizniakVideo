# ZalizniakVideo

_Created: 14-04-2026 · Last updated: 01-08-2026_

Статический **только-видео** каталог публичных лекций академика
**А. А. Зализняка** (1935–2017): индекс + отдельная HTML-страница на каждое
YouTube-видео.

## Прямые ссылки

| Что | URL |
|---|---|
| **Этот сайт (индекс)** | [https://gasyoun.github.io/ZalizniakVideo/](https://gasyoun.github.io/ZalizniakVideo/) |
| **Страница одного видео** | `https://gasyoun.github.io/ZalizniakVideo/video/<youtube-id>/` |
| **JSON API** | [data/catalog.json](https://gasyoun.github.io/ZalizniakVideo/data/catalog.json) |
| **Корпусная галерея BookIndex** (указатель, KWIC, фильтры по главам книги) | [BookIndex `#v4/materials/video`](https://gasyoun.github.io/BookIndex/aaz-index.html#v4/materials/video) |

## Что здесь есть / чего нет

**Есть**

- `index.html` — список ~175 уникальных роликов (поиск, тема, сортировка)
- `video/<id>/index.html` — страница ролика с embed (youtube-nocookie), метаданные, ссылки
- `data/catalog.json` — машиночитаемый каталог
- данные из [BookIndex](https://github.com/gasyoun/BookIndex) `video_catalog` + `video_pipeline.json`

**Нет (намеренно)**

- полных расшифровок (они в конвейере BookIndex / том II; 27/176 text-links на момент выгрузки)
- книжного указателя, KWIC, симуляторов — это BookIndex
- «записей глав» книги «Из жизни слов и языков» — это **другие** публичные выступления

## Сборка

Нужен соседний клон `../BookIndex` (или `BOOKINDEX_ROOT`).

```bash
python scripts/build_site.py
```

Переменные окружения:

- `BOOKINDEX_ROOT` — путь к BookIndex
- `SITE_BASE` — канонический origin (по умолчанию `https://gasyoun.github.io/ZalizniakVideo`)

## Честные счётчики (сборка 01-08-2026)

| Метрика | Значение |
|---|---:|
| Строк `video_catalog` (raw) | 191 |
| Уникальных YouTube id (страниц) | 175 |
| Видео в pipeline | 176 |
| Коллизии «много заголовков → один id» | 3 |
| Суммарная длительность (уникальные) | ~см. `data/stats.json` |

Коллизии id (`Tz3T7IxsbLU`, `xIoXVxahvDY`, `cJp5ZrnGivw`) — дефект сопоставления в источнике; на странице ролика перечислены все «висящие» заголовки. Исправление — в BookIndex (волна V0).

## Лицензия

Код сайта — [Apache License 2.0](https://github.com/gasyoun/ZalizniakVideo/blob/main/LICENSE).
Сами видео принадлежат правообладателям YouTube/архивов; здесь только индекс и ссылки.
Разметка сущностей и выдержки из расшифровок наследуются из политики данных BookIndex
([LICENSE-DATA.md](https://github.com/gasyoun/BookIndex/blob/main/LICENSE-DATA.md)).

_Dr. Mārcis Gasūns_
