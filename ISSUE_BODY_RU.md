## Контекст

Нужен **отдельный сайт только с видео** академика А. А. Зализняка: индекс + страница на каждый ролик — без корпусной оболочки BookIndex (указатель, KWIC, симуляторы).

## Прямые ссылки

| | |
|---|---|
| **Индекс (ZalizniakVideo)** | https://gasyoun.github.io/ZalizniakVideo/ |
| **Пример страницы ролика** | https://gasyoun.github.io/ZalizniakVideo/video/tv87ggs0yq4/ |
| **Галерея внутри BookIndex** | https://gasyoun.github.io/BookIndex/aaz-index.html#v4/materials/video |
| **Каталог JSON** | https://gasyoun.github.io/ZalizniakVideo/data/catalog.json |

## Что сделано (H2135)

- Сгенерирован статический сайт из `BookIndex/app_data.json` → `video_catalog` + `data/video_pipeline.json`
- **175** страниц `video/<youtube-id>/index.html` + корневой `index.html` (поиск / тема / сортировка)
- Embed через `youtube-nocookie`, без autoplay
- Машиночитаемый `data/catalog.json`
- Коллизии id помечены на карточках и на детальных страницах

## Известные ограничения (не баги сайта, а данные)

1. **3 YouTube id** несут по несколько разных названий семинаров (серия «История русского ударения»): `xIoXVxahvDY` (×8), `Tz3T7IxsbLU` (×6), `cJp5ZrnGivw` (×5). На YouTube — одна запись; «лишние» заголовки — ошибка сопоставления в BookIndex. Исправление: волна **V0** в BookIndex ([PLAN_BOOKINDEX_UI_CLEANUP_VIDEO_2026Q3](https://github.com/gasyoun/BookIndex/blob/main/docs/PLAN_BOOKINDEX_UI_CLEANUP_VIDEO_2026Q3.md)).
2. **Даты** заполнены не у всех роликов; сортировка «по дате» осмысленна только для размеченных.
3. **`timecodes` в каталоге пусты**; минуты на сущностях — из BookIndex/KWIC, не с этой площадки.
4. **Полных расшифровок здесь нет** (конвейер том II: ~27/176 text-links на момент выгрузки).
5. Счётчики: raw 191 · unique 175 · pipeline 176 · продуктовое «~200» — округление.

## Зачем отдельный репозиторий

BookIndex — тяжёлая корпусная оболочка. ZalizniakVideo — лёгкий **shareable** индекс «только видео» с стабильными URL вида `/video/<id>/`, пригодный для QR, печати (полосы 4–5 спутника) и внешних ссылок без hash-роутера SPA.

## Следующие шаги (не в этом PR)

- [ ] Починить коллизии id в BookIndex (V0) и пересобрать этот сайт
- [ ] Подтянуть даты/темы из первичных листов
- [ ] Опционально: бейдж стадии конвейера + ссылка на dashboard BookIndex
- [ ] Когда появятся text-links — решить, публиковать ли выдержки (права)

---

**Модель:** Grok 4.5 (`grok-4.5`) · handoff H2135
