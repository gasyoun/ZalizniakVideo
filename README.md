# ZalizniakVideo

_Created: 14-04-2026 · Last updated: 03-08-2026_

Статический научно-редакционный каталог публичных видеозаписей, связанных с
работами **А. А. Зализняка** (1935–2017). Архив рассчитан на читателей,
исследователей и студентов. Каждая из 175 записей получает замороженный
трёхзначный номер и постоянную страницу.

## Прямые ссылки

| Что | URL |
|---|---|
| **Этот сайт (индекс)** | [https://gasyoun.github.io/ZalizniakVideo/](https://gasyoun.github.io/ZalizniakVideo/) |
| **Каноническая карточка** | `https://gasyoun.github.io/ZalizniakVideo/v/<NNN>/` |
| **JSON API v1** | [data/catalog.json](https://gasyoun.github.io/ZalizniakVideo/data/catalog.json) |
| **JSON API v2** | [data/catalog.v2.json](https://gasyoun.github.io/ZalizniakVideo/data/catalog.v2.json) |
| **Корпусная галерея BookIndex** (указатель, KWIC, фильтры по главам книги) | [BookIndex `#v4/materials/video`](https://gasyoun.github.io/BookIndex/aaz-index.html#v4/materials/video) |

## Что здесь есть / чего нет

**Есть**

- `index.html` — 175 карточек, поиск и фильтры по теме, типу, серии, году и расшифровке
- `v/<NNN>/index.html` — каноническая архивная карточка записи
- `video/<youtube-id>/index.html` — совместимый адрес-переход с `noindex, follow`
- `assets/thumbs/<NNN>.jpg` — локальный кэш обложек; внешний запрос до запуска плеера не выполняется
- `data/catalog.json` — совместимый каталог v1 со старыми путями
- `data/catalog.v2.json` — номера, канонические пути и научно-редакционные поля
- данные из публичного экспорта [BookIndex](https://github.com/gasyoun/BookIndex)

**Нет (намеренно)**

- полных расшифровок: каталог публикует только статус и проверенную публичную ссылку, когда она существует
- книжного указателя, KWIC, симуляторов — это BookIndex
- «записей глав» книги «Из жизни слов и языков» — это **другие** публичные выступления

## Сборка

Предпочтительный входной файл находится в соседнем репозитории BookIndex:
`../BookIndex/data/video_catalog_public.json`. Его можно указать
явно. Если файла ещё нет, генератор использует проверенный `data/catalog.json`
как миграционный набор.

```bash
python scripts/build_site.py --catalog ../BookIndex/data/video_catalog_public.json
```

Обычная сборка работает без сети и завершается ошибкой, если хотя бы одной
локальной обложки нет. Только для первоначального заполнения или осознанного
обновления кэша используется:

```bash
python scripts/build_site.py --catalog ../BookIndex/data/video_catalog_public.json --fetch-thumbnails
```

Переменная окружения:

- `SITE_BASE` — канонический origin (по умолчанию `https://gasyoun.github.io/ZalizniakVideo`)
- `BOOKINDEX_VIDEO_CATALOG` — альтернативный путь к публичному экспорту BookIndex

Тесты:

```bash
python -m unittest discover -s tests -v
python scripts/validate_site.py
```

## Локальный просмотр

Открывайте сайт через локальный HTTP-сервер из корня репозитория:

```bash
python -m http.server 8000
```

Затем перейдите на `http://localhost:8000/`. Не открывайте страницы через
`file://`: YouTube отклоняет такой embed без HTTP referrer и показывает
`Error 153`. Плеер в обычном режиме создаётся только после нажатия кнопки и
никогда не запускает видео автоматически.

## Честные счётчики (сборка 03-08-2026)

| Метрика | Значение |
|---|---:|
| Строк источника | 192 |
| Уникальных YouTube id | 175 |
| Канонических карточек `/v/NNN/` | 175 |
| Совместимых адресов `/video/<id>/` | 175 |
| Неразрешённых строк источника | 16 |

Неразрешённые строки остаются в публичном экспорте BookIndex для аудита, но не
получают ложных видеокарточек. Номера 001–175 заморожены в реестре BookIndex.

## Лицензия

Код сайта — [Apache License 2.0](https://github.com/gasyoun/ZalizniakVideo/blob/main/LICENSE).
Сами видео принадлежат правообладателям YouTube/архивов; здесь только индекс и ссылки.
Разметка сущностей и выдержки из расшифровок наследуются из политики данных BookIndex
([LICENSE-DATA.md](https://github.com/gasyoun/BookIndex/blob/main/LICENSE-DATA.md)).

_Dr. Mārcis Gasūns_
