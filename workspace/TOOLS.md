# TOOLS.md - Local Notes

Skills define _how_ tools work. This file is for _your_ specifics — the stuff that's unique to your setup.

## What Goes Here

Things like:

- Camera names and locations
- SSH hosts and aliases
- Preferred voices for TTS
- Speaker/room names
- Device nicknames
- Anything environment-specific

## Examples

```markdown
### Cameras

- living-room → Main area, 180° wide angle
- front-door → Entrance, motion-triggered

### SSH

- home-server → 192.168.1.100, user: admin

### TTS

- Preferred voice: "Nova" (warm, slightly British)
- Default speaker: Kitchen HomePod
```

## Why Separate?

Skills are shared. Your setup is yours. Keeping them apart means you can update skills without losing your notes, and share skills without leaking your infrastructure.

---

## Напоминания (Reminders)

**ВАЖНО:** Когда пользователь просит напомнить через точное время — ВСЕГДА создавай напоминание как **isolated agentTurn**, а НЕ как systemEvent в main сессии!

- `sessionTarget: "isolated"` + `payload.kind: "agentTurn"` — срабатывает точно по времени, независимо от heartbeat
- `sessionTarget: "main"` + `payload.kind: "systemEvent"` — ждёт heartbeat, может опоздать!

Пример правильного напоминания:
```json
{
  "sessionTarget": "isolated",
  "payload": {
    "kind": "agentTurn",
    "message": "Напомни Наталии принять витаминки!"
  },
  "delivery": { "mode": "announce" }
}
```

---

## Обработка данных (парсинг, скрейпинг, массовые операции)

**ВАЖНО:** Любые задачи по массовой обработке данных (парсинг парфюмов, скрейпинг, batch-операции) — ВСЕГДА запускай через **субагента** (`sessions_spawn`). Это экономит контекст основной сессии и предотвращает раннюю компакцию.

Примеры задач для субагента:
- Скрейпинг данных с Fragrantica/Parfumo
- Массовое обновление HTML-файлов
- Парсинг и обработка больших объёмов текста
- Любые циклы по 10+ элементам

---

## iCloud Calendar

**Календари Наталии:**
- Coaching, Семья ⚠️, Work, Artjom, ToDo, Anton, Trainings, Экспонента, Lashes, Koolitus, Кинетический аналитик, Home, Голос, Travel, Напоминания ⚠️, Наш ⚠️

**ВАЖНО:** При добавлении события в календарь — ВСЕГДА спрашивай, в какой именно календарь добавить, если это не указано явно в сообщении.

**Команда:**
```bash
cd /data/workspace/skills/icloud-calendar && uv run --with caldav --with vobject python3 ical.py <command> [args]
```

---

---

## Каталог фильмов

**Расположение:** `/data/workspace/pages/movies/`
**URL:** `nataliakatsalukha.com/pages/movies/`

### Скрипты:
```bash
# Найти и скачать постер (Film.ru → TMDB → Wikipedia)
/data/workspace/pages/movies/poster.sh "<slug-или-название>" "<filename.jpg>"

# Добавить фильм в каталог
/data/workspace/pages/movies/add.sh "<title>" <year> "<Genre1,Genre2>" "<poster.jpg>" [movie|series] [watchlist|watched]
```

### Порядок добавления:
1. Определить фильм/сериал из скриншота
2. `poster.sh` — попробовать найти постер (slug на film.ru через транслит)
3. Если не найден — сохранить скриншот пользователя
4. `add.sh` — добавить в movies.json
5. По умолчанию: status=watchlist, type=movie

### Источники постеров (приоритет):
1. **Film.ru** — slug: `{название-транслитом}`, суффиксы `-0`..`-5`
2. **TMDB** — поиск по англ. названию
3. **Wikipedia** — `upload.wikimedia.org`
4. **Скриншот** — fallback

---

---

## Сортировка скриншотов

**База данных:** `/data/workspace/pages/screenshots/index.json`
**Скриншоты:** `/data/workspace/pages/screenshots/<category>/`

### Категории:
| Папка | Emoji | Название | Каталог (веб) |
|-------|-------|----------|---------------|
| books | 📚 | Книги | /pages/books/ |
| hair | 💇‍♀️ | Волосы | /pages/hair/ |
| cosmetics-skincare | 🧴 | Уходовая косметика | /pages/skincare/ |
| cosmetics-decorative | 💄 | Декоративная косметика | /pages/decorative/ |
| perfume | 🌸 | Парфюм | /pages/perfume/ |
| coaching | 🎯 | Коучинг | — (через чат) |
| blog | ✍️ | Ведение блога | — |
| fashion | 👗 | Мода | — |
| home | 🏠 | Дом | — |
| travel-ideas | 🏖 | Путешествия | — |
| food | 🍽 | Еда | — |
| games | 🎲 | Игры | — |
| health | 💊 | Здоровье | — |
| finds | 💡 | Находки | — (теги: #девайс, #подарок, #для_себя, #для_дома) |
| places-selfcare | 📍 | Места: уход | — |

### Алгоритм при получении скриншота:
1. Проанализировать изображение
2. Определить категорию (если уверен >90% — сохранить и сказать; иначе — спросить)
3. Сохранить: `cp <inbound> /data/workspace/pages/screenshots/<category>/<slug>.jpg`
4. Добавить запись в `index.json`
5. **Если есть веб-каталог** → найти красивое фото продукта из интернета, скачать в `/pages/<catalog>/img/`, добавить в HTML
6. Сообщить результат

### Для каталогов с веб-страницами:
- Картинки: красивые продуктовые фото (не скриншоты!) в `/pages/<catalog>/img/`
- Стиль: Bebas Neue заголовки (англ.), Playfair Display названия, Inter текст
- Заголовки каталогов: BOOK COLLECTION, HAIR CARE, SKINCARE, MAKEUP COLLECTION, PERFUME COLLECTION, MOVIE COLLECTION

### Использование для рекомендаций:
Когда Наталия спрашивает о теме (волосы, косметика и т.д.) — искать в index.json по тегам и категориям, показывать релевантную информацию из коллекции.

---

---

## Fragrantica (парфюмерный каталог)

**ВАЖНО:** Fragrantica блокирует обычные запросы (Cloudflare). Всегда используй **ScrapingBee** для доступа:

```bash
curl -s "https://app.scrapingbee.com/api/v1/?api_key=${SCRAPINGBEE_API_KEY}&url=<URL>&render_js=true"
```

**Workflow при добавлении парфюма:**
1. Получить ссылку/фото от Наталии
2. **ВСЕГДА запускать субагента** для: поиска на Fragrantica, скачивания фото, заполнения всех полей
3. Извлечь: бренд, название, год, ноты (top/mid/base), аккорды (с весами и цветами!), рейтинг, семейство, парфюмер, концентрация, стойкость, шлейф
4. **Фото: ВСЕГДА скачивать из интернета** (не использовать скрины от пользователя!)
   - Fragrantica: `https://fimgs.net/mdimg/perfume/375x500.{ID}.jpg` (ID из URL страницы)
   - Альтернатива: Google Images, parfumo.net
   - Сохранить в `/data/workspace/pages/perfume/img/`
5. Обновить `/data/workspace/pages/perfume/perfumes.json` **строго по шаблону Delina**
6. Закоммитить

**ШАБЛОН (эталон — Delina). Все 23 поля ОБЯЗАТЕЛЬНЫ:**
```json
{
  "brand": "string",
  "name": "string", 
  "notes": "string — краткие ноты через запятую",
  "desc": "string — описание 1-2 предложения",
  "tags": ["floral", "woody", "fruity", "gourmand", "fresh", "oriental"],
  "source": "string",
  "fav": false,
  "price": "string (~250€ или '')",
  "img": "img/filename.jpg",
  "pyramid": {"top": "string", "mid": "string", "base": "string"},
  "accords": [{"name": "русское название", "w": 100, "color": "#hex"}],
  "rating": 0,
  "votes": 0,
  "longevity": "string (6–8ч или '')",
  "sillage": "string (Сильный/Средний/Лёгкий или '')",
  "daytime": ["day", "night"],
  "seasons": ["spring", "summer", "autumn", "winter"],
  "year": 2024,
  "perfumer": "string",
  "concentration": "string (EDP/EDT/Parfum)",
  "gender": "string (Ж/М/Унисекс)",
  "family": "string (Цветочный/Восточный/Древесный)"
}
```

**ВАЖНО:** Фото должны быть эстетичными и органично смотреться на страничке — только качественные изображения из интернета!

---

Add whatever helps you do your job. This is your cheat sheet.
