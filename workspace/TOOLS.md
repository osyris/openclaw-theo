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

Add whatever helps you do your job. This is your cheat sheet.
