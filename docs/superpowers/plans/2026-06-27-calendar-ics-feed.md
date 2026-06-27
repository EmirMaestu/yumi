# Feed de calendario (.ics) — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que cada usuario pueda suscribir su calendario externo (Google/Apple/Outlook) a un feed `.ics` de Yumi y ver ahí sus eventos y recordatorios.

**Architecture:** Endpoint público `GET /api/cal/{token}.ics` (auth por token secreto en la URL) que genera el iCalendar al vuelo desde SQLite con un módulo puro `calfeed.build_ics`. Endpoints con sesión para obtener/rotar la URL. Tarjeta en la pantalla Agenda del frontend para copiar la URL.

**Tech Stack:** Python (FastAPI, SQLite), librería `icalendar`, pytest (ya en el venv), React + TanStack Query.

**Spec:** `docs/superpowers/specs/2026-06-27-calendar-ics-feed-design.md`

---

## Contexto de entorno (LEER antes de empezar)

- **No hay Python local.** Los tests Python corren en el **venv del VPS**: `~/asistente/venv/bin/python -m pytest`. El flujo por tarea Python es: editar local → `scp` a `~/asistente/` → correr pytest por SSH.
- **Deploy backend:** `tr -d '\r' < archivo.py | ssh emir@217.76.48.219 'cat > ~/asistente/archivo.py.new && ~/asistente/venv/bin/python -m py_compile ~/asistente/archivo.py.new'` → `diff --strip-trailing-cr` → backup + `mv` → el **usuario** corre `sudo systemctl restart asistente asistente-web`.
- **Deploy frontend:** `npm run build` en `web-react/` → `scp -r dist/* emir@217.76.48.219:~/asistente/webapp/` → el usuario corre `sudo cp -r ~/asistente/webapp /var/www/juntu`.
- **Multi-inquilino:** todo se scopea por `user_id` propio (ya decidido: el feed es solo del usuario, no del hogar).
- VPS: `emir@217.76.48.219`. DB: `~/asistente/data.db`.

---

## Estructura de archivos

| Archivo | Responsabilidad | Acción |
|---|---|---|
| `vps_current/calfeed.py` | Generador puro `build_ics(eventos, recordatorios, tzname) -> bytes` | **Crear** |
| `vps_current/tests/test_calfeed.py` | Tests del generador (pytest) | **Crear** |
| `vps_current/main.py` | Migración: columna `users.cal_token` + índice | Modificar |
| `vps_current/web.py` | 3 endpoints + helper de token | Modificar |
| `web-react/src/components/CalendarSubscribe.tsx` | Tarjeta "Suscribir a mi calendario" | **Crear** |
| `web-react/src/routes/Agenda.tsx` | Montar la tarjeta | Modificar |
| `.env` (VPS) | `PUBLIC_BASE_URL` | Agregar |
| venv (VPS) | dependencia `icalendar` | Instalar |

---

## Task 0: Dependencia `icalendar` en el venv

**Files:** ninguno (setup de entorno).

- [ ] **Step 1: Instalar icalendar en el venv del VPS**

Run:
```bash
ssh emir@217.76.48.219 '~/asistente/venv/bin/pip install icalendar && ~/asistente/venv/bin/python -c "import icalendar; print(icalendar.__version__)"'
```
Expected: imprime una versión (≥5.0.11, para `add_missing_timezones`).

---

## Task 1: Generador `calfeed.build_ics` (TDD)

**Files:**
- Create: `vps_current/calfeed.py`
- Test: `vps_current/tests/test_calfeed.py`

- [ ] **Step 1: Escribir los tests que fallan**

Crear `vps_current/tests/test_calfeed.py`:
```python
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from icalendar import Calendar
import calfeed


def _parse(b):
    return Calendar.from_ical(b)


def test_empty_is_valid():
    cal = _parse(calfeed.build_ics([], []))
    assert cal.get("version") == "2.0"
    assert len(list(cal.walk("VEVENT"))) == 0


def test_evento_renders_vevent():
    out = calfeed.build_ics(
        [{"id": 1, "title": "Cena con Ana", "starts_at": "2026-07-01T21:00",
          "location": "Casa", "notes": "traer vino"}], [])
    ev = list(_parse(out).walk("VEVENT"))[0]
    assert str(ev.get("summary")) == "Cena con Ana"
    assert str(ev.get("location")) == "Casa"
    assert str(ev.get("uid")) == "yumi-evento-1@yumi"
    dt = ev.get("dtstart").dt
    assert dt.hour == 21 and dt.tzinfo is not None
    assert (ev.get("dtend").dt - dt).seconds == 3600


def test_recordatorio_has_alarm():
    out = calfeed.build_ics([], [{"id": 5, "text": "Pagar luz",
                                  "remind_at": "2026-07-02 09:00", "recurrence": None}])
    ev = list(_parse(out).walk("VEVENT"))[0]
    assert str(ev.get("uid")) == "yumi-rec-5@yumi"
    assert len(list(ev.walk("VALARM"))) == 1


def test_recurrence_emits_rrule():
    out = calfeed.build_ics([], [{"id": 6, "text": "Pastilla",
                                  "remind_at": "2026-07-02T08:00", "recurrence": "daily"}])
    ev = list(_parse(out).walk("VEVENT"))[0]
    assert ev.get("rrule").get("FREQ") == ["DAILY"]


def test_broken_item_skipped():
    out = calfeed.build_ics([{"id": 9, "title": "sin fecha", "starts_at": None}], [])
    assert len(list(_parse(out).walk("VEVENT"))) == 0


def test_has_vtimezone():
    out = calfeed.build_ics([{"id": 1, "title": "x", "starts_at": "2026-07-01T21:00"}], [])
    assert len(list(_parse(out).walk("VTIMEZONE"))) >= 1


def test_escaping_roundtrips():
    out = calfeed.build_ics([{"id": 1, "title": "Pagar, urgente\nantes de las 5",
                              "starts_at": "2026-07-01T10:00"}], [])
    ev = list(_parse(out).walk("VEVENT"))[0]
    assert str(ev.get("summary")) == "Pagar, urgente\nantes de las 5"
```

- [ ] **Step 2: Correr los tests y verificar que fallan**

Run:
```bash
scp vps_current/tests/test_calfeed.py emir@217.76.48.219:~/asistente/tests/test_calfeed.py
ssh emir@217.76.48.219 'cd ~/asistente && venv/bin/python -m pytest tests/test_calfeed.py -v'
```
(Si `~/asistente/tests` no existe: `ssh emir@217.76.48.219 'mkdir -p ~/asistente/tests'` primero.)
Expected: FAIL — `ModuleNotFoundError: No module named 'calfeed'`.

- [ ] **Step 3: Implementar `calfeed.py`**

Crear `vps_current/calfeed.py`:
```python
"""Generador de feed iCalendar (.ics) para Yumi. Módulo puro (sin DB), testeable."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from icalendar import Calendar, Event, Alarm

_FREQ = {"daily": "DAILY", "weekly": "WEEKLY", "monthly": "MONTHLY"}


def _parse_local(s, tz):
    """Parsea 'YYYY-MM-DDTHH:MM[:SS]' o 'YYYY-MM-DD HH:MM' (naive) como hora local tz. None si no se puede."""
    if not s:
        return None
    s = str(s).strip().replace(" ", "T")
    for length, fmt in ((19, "%Y-%m-%dT%H:%M:%S"), (16, "%Y-%m-%dT%H:%M"), (10, "%Y-%m-%d")):
        try:
            return datetime.strptime(s[:length], fmt).replace(tzinfo=tz)
        except ValueError:
            continue
    return None


def build_ics(eventos, recordatorios, tzname="America/Argentina/Buenos_Aires"):
    """Devuelve bytes (UTF-8) de un VCALENDAR con los eventos y recordatorios dados.
    eventos: dicts {id, title, starts_at, location, notes}
    recordatorios: dicts {id, text, remind_at, recurrence}"""
    tz = ZoneInfo(tzname)
    cal = Calendar()
    cal.add("prodid", "-//Yumi//Calendar Feed//ES")
    cal.add("version", "2.0")
    cal.add("calscale", "GREGORIAN")
    cal.add("method", "PUBLISH")
    cal["x-wr-calname"] = "Yumi"
    cal["x-wr-timezone"] = tzname

    for e in (eventos or []):
        start = _parse_local(e.get("starts_at"), tz)
        if not start:
            continue
        ev = Event()
        ev.add("uid", f"yumi-evento-{e['id']}@yumi")
        ev.add("summary", e.get("title") or "Evento")
        ev.add("dtstart", start)
        ev.add("dtend", start + timedelta(hours=1))
        if e.get("location"):
            ev.add("location", e["location"])
        if e.get("notes"):
            ev.add("description", e["notes"])
        cal.add_component(ev)

    for r in (recordatorios or []):
        start = _parse_local(r.get("remind_at"), tz)
        if not start:
            continue
        ev = Event()
        ev.add("uid", f"yumi-rec-{r['id']}@yumi")
        ev.add("summary", r.get("text") or "Recordatorio")
        ev.add("dtstart", start)
        ev.add("dtend", start + timedelta(minutes=30))
        freq = _FREQ.get((r.get("recurrence") or "").strip().lower())
        if freq:
            ev.add("rrule", {"freq": [freq]})
        alarm = Alarm()
        alarm.add("action", "DISPLAY")
        alarm.add("description", r.get("text") or "Recordatorio")
        alarm.add("trigger", timedelta(0))
        ev.add_component(alarm)
        cal.add_component(ev)

    try:
        cal.add_missing_timezones()  # agrega VTIMEZONE de Buenos Aires
    except Exception:
        pass
    return cal.to_ical()
```

- [ ] **Step 4: Subir y correr los tests; verificar que pasan**

Run:
```bash
scp vps_current/calfeed.py emir@217.76.48.219:~/asistente/calfeed.py
ssh emir@217.76.48.219 'cd ~/asistente && venv/bin/python -m pytest tests/test_calfeed.py -v'
```
Expected: PASS (7 passed).

- [ ] **Step 5: Commit**

```bash
git add vps_current/calfeed.py vps_current/tests/test_calfeed.py
git commit -m "feat(cal): generador de feed iCalendar (calfeed.build_ics) + tests"
```

---

## Task 2: Migración `users.cal_token` (main.py)

**Files:**
- Modify: `vps_current/main.py` (bloque `_ALTERS` de `users` + índice)

- [ ] **Step 1: Agregar la columna a `_ALTERS["users"]`**

En `vps_current/main.py`, en el dict `_ALTERS`, agregar `("cal_token", "TEXT")` a la lista de `"users"`:
```python
    _ALTERS = {
        "users": [("plan", "TEXT DEFAULT 'free'"),
                  ("referral_code", "TEXT"),
                  ("referred_by", "INTEGER"),
                  ("channel", "TEXT DEFAULT 'telegram'"),
                  ("wa_id", "TEXT"),
                  ("household_id", "INTEGER"),
                  ("link_code", "TEXT"),
                  ("link_code_exp", "TEXT"),
                  ("cal_token", "TEXT")],
```

- [ ] **Step 2: Agregar índice único del token**

En `main.py`, junto a los otros `CREATE INDEX` del init (después del loop de `_ALTERS`, donde están `idx_users_refcode` etc.), agregar:
```python
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_cal_token ON users(cal_token)")
```
(SQLite permite múltiples NULL en un índice único, así que las filas sin token no chocan.)

- [ ] **Step 3: Validar compilación + migración sobre copia de la DB**

Run:
```bash
tr -d '\r' < vps_current/main.py | ssh emir@217.76.48.219 'cat > ~/asistente/main.py.new && ~/asistente/venv/bin/python -m py_compile ~/asistente/main.py.new && echo OK'
ssh emir@217.76.48.219 'cp ~/asistente/data.db /tmp/caltest.db && ~/asistente/venv/bin/python -c "import sqlite3; c=sqlite3.connect(\"/tmp/caltest.db\"); c.execute(\"ALTER TABLE users ADD COLUMN cal_token TEXT\"); c.execute(\"CREATE UNIQUE INDEX IF NOT EXISTS idx_users_cal_token ON users(cal_token)\"); print([r[1] for r in c.execute(\"PRAGMA table_info(users)\")]); rm=__import__(\"os\").remove" ; rm -f /tmp/caltest.db'
```
Expected: `OK` y la lista de columnas incluye `cal_token`.

- [ ] **Step 4: Commit** (se despliega junto con web.py en Task 3)

```bash
git add vps_current/main.py
git commit -m "feat(cal): columna users.cal_token + índice (migración)"
```

---

## Task 3: Endpoints del feed (web.py)

**Files:**
- Modify: `vps_current/web.py` (agregar `PUBLIC_BASE_URL`, helper y 3 endpoints; cerca de los endpoints `/api/push/*`)

- [ ] **Step 1: Agregar config + helper + endpoints**

En `vps_current/web.py`, agregar (después del bloque de endpoints `/api/push/*`):
```python
# ─── Feed de calendario (.ics) ─────────────────────────────────────────────
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "https://asistente.emir-maestu.site").rstrip("/")


def _cal_token_for(conn, user_id):
    row = conn.execute("SELECT cal_token FROM users WHERE id=?", (user_id,)).fetchone()
    tok = row["cal_token"] if row and row["cal_token"] else None
    if not tok:
        tok = secrets.token_urlsafe(24)
        conn.execute("UPDATE users SET cal_token=? WHERE id=?", (tok, user_id))
        conn.commit()
    return tok


@app.get("/api/cal/url")
def cal_url(user=Depends(require_user)):
    with db() as conn:
        tok = _cal_token_for(conn, user["id"])
    return {"url": f"{PUBLIC_BASE_URL}/api/cal/{tok}.ics"}


@app.post("/api/cal/regenerate")
def cal_regenerate(user=Depends(require_user)):
    tok = secrets.token_urlsafe(24)
    with db() as conn:
        conn.execute("UPDATE users SET cal_token=? WHERE id=?", (tok, user["id"]))
        conn.commit()
    return {"url": f"{PUBLIC_BASE_URL}/api/cal/{tok}.ics"}


@app.get("/api/cal/{token}.ics")
def cal_feed(token: str):
    import calfeed
    with db() as conn:
        u = conn.execute("SELECT id FROM users WHERE cal_token=? AND active=1", (token,)).fetchone()
        if not u:
            raise HTTPException(404, "No encontrado")
        uid = u["id"]
        desde = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        eventos = [dict(r) for r in conn.execute(
            "SELECT id, title, starts_at, location, notes FROM eventos "
            "WHERE user_id=? AND substr(starts_at,1,10) >= ? ORDER BY starts_at", (uid, desde)).fetchall()]
        recs = [dict(r) for r in conn.execute(
            "SELECT id, text, remind_at, recurrence FROM recordatorios "
            "WHERE user_id=? AND substr(REPLACE(remind_at,' ','T'),1,10) >= ? ORDER BY remind_at",
            (uid, desde)).fetchall()]
    body = calfeed.build_ics(eventos, recs)
    return Response(content=body, media_type="text/calendar; charset=utf-8",
                    headers={"Content-Disposition": 'inline; filename="yumi.ics"'})
```

> `Response`, `datetime`, `timedelta`, `secrets`, `os` ya están importados en web.py (verificado). El path `/api/cal/{token}.ics` matchea token = la parte antes de `.ics` (Starlette trata `.ics` como literal). Caddy rutea `/api/*` a uvicorn, sin cookie.

- [ ] **Step 2: Validar compilación**

Run:
```bash
tr -d '\r' < vps_current/web.py | ssh emir@217.76.48.219 'cat > ~/asistente/web.py.new && ~/asistente/venv/bin/python -m py_compile ~/asistente/web.py.new && echo OK'
```
Expected: `OK`.

- [ ] **Step 3: Setear `PUBLIC_BASE_URL` en el .env del VPS**

Run:
```bash
ssh emir@217.76.48.219 'cd ~/asistente && grep -q "^PUBLIC_BASE_URL=" .env || printf "\nPUBLIC_BASE_URL=https://asistente.emir-maestu.site\n" >> .env; grep PUBLIC_BASE_URL .env'
```
Expected: imprime `PUBLIC_BASE_URL=https://asistente.emir-maestu.site`.

- [ ] **Step 4: Desplegar backend (calfeed.py ya está; swap main.py + web.py)**

Run:
```bash
ssh emir@217.76.48.219 'cd ~/asistente && diff --strip-trailing-cr main.py main.py.new; diff --strip-trailing-cr web.py web.py.new'
ssh emir@217.76.48.219 'cd ~/asistente && ts=$(date +%Y%m%d-%H%M%S) && cp main.py main.py.bak-$ts && cp web.py web.py.bak-$ts && mv main.py.new main.py && mv web.py.new web.py && venv/bin/python -m py_compile main.py web.py calfeed.py && echo swapped'
```
Luego **el usuario** corre:
```bash
ssh -t emir@217.76.48.219 'sudo systemctl restart asistente asistente-web && systemctl is-active asistente asistente-web'
```
Expected: `active` ×2. El restart del bot crea la columna `cal_token`.

- [ ] **Step 5: Verificar el endpoint en vivo (curl)**

Necesitás una sesión válida. Más simple: obtené el token de un usuario directo de la DB y pegá el feed:
```bash
ssh emir@217.76.48.219 'cd ~/asistente && venv/bin/python -c "import sqlite3,secrets; c=sqlite3.connect(\"data.db\"); t=secrets.token_urlsafe(24); c.execute(\"UPDATE users SET cal_token=? WHERE id=1\",(t,)); c.commit(); print(t)"'
# con ese token:
curl -s "https://asistente.emir-maestu.site/api/cal/<TOKEN>.ics" | head -20
curl -s -o /dev/null -w "%{http_code}\n" "https://asistente.emir-maestu.site/api/cal/tokenfalso.ics"
```
Expected: el primero arranca con `BEGIN:VCALENDAR` y contiene `VTIMEZONE`/`VEVENT`; el segundo devuelve `404`.

- [ ] **Step 6: Commit** (ya commiteado main.py en Task 2; commitear web.py)

```bash
git add vps_current/web.py
git commit -m "feat(cal): endpoints /api/cal/{url,regenerate,feed.ics}"
```

---

## Task 4: Tarjeta "Suscribir a mi calendario" (frontend)

**Files:**
- Create: `web-react/src/components/CalendarSubscribe.tsx`
- Modify: `web-react/src/routes/Agenda.tsx` (import + montar la tarjeta arriba)

- [ ] **Step 1: Crear el componente**

Crear `web-react/src/components/CalendarSubscribe.tsx`:
```tsx
import { useState } from 'react'
import { apiGet, apiPost } from '../lib/api'
import Card from './ui/Card'

export default function CalendarSubscribe() {
  const [open, setOpen] = useState(false)
  const [url, setUrl] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [copied, setCopied] = useState(false)

  const load = async () => {
    setOpen(true)
    if (url) return
    setLoading(true)
    try {
      const r = await apiGet<{ url: string }>('/api/cal/url')
      setUrl(r.url)
    } finally {
      setLoading(false)
    }
  }

  const regenerate = async () => {
    if (!window.confirm('Vas a generar un link nuevo. El calendario que ya tengas suscripto va a dejar de actualizarse. ¿Seguir?')) return
    setLoading(true)
    try {
      const r = await apiPost<{ url: string }>('/api/cal/regenerate')
      setUrl(r.url)
      setCopied(false)
    } finally {
      setLoading(false)
    }
  }

  const copy = () => {
    if (!url) return
    navigator.clipboard?.writeText(url).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    }).catch(() => {})
  }

  if (!open) {
    return (
      <button onClick={load} style={linkBtn}>📅 Suscribir a mi calendario</button>
    )
  }

  return (
    <Card style={{ display: 'grid', gap: 10, background: 'var(--color-mist)', border: 'none' }}>
      <div style={{ fontSize: 14, fontWeight: 600 }}>📅 Suscribir a mi calendario</div>
      <div style={{ fontSize: 12.5, color: 'var(--color-sage)' }}>
        Pegá este link en Google/Apple/Outlook Calendar y vas a ver tus eventos y recordatorios de Yumi ahí.
        (Se actualiza cada varias horas, no al instante.)
      </div>
      {loading && <div style={{ fontSize: 13 }}>Cargando…</div>}
      {url && (
        <>
          <div style={{ fontSize: 12, wordBreak: 'break-all', background: 'var(--color-linen)', padding: 8, borderRadius: 8 }}>{url}</div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <button onClick={copy} style={primaryBtn}>{copied ? '¡Copiado!' : 'Copiar link'}</button>
            <button onClick={regenerate} style={ghostBtn}>Regenerar</button>
          </div>
          <div style={{ fontSize: 11.5, color: 'var(--color-sage)', lineHeight: 1.5 }}>
            <b>Google:</b> Otros calendarios → Desde URL → pegá el link.<br />
            <b>iPhone:</b> Ajustes → Calendario → Cuentas → Agregar cuenta → Otro → Agregar calendario suscrito.
          </div>
        </>
      )}
    </Card>
  )
}

const linkBtn: React.CSSProperties = {
  background: 'transparent', border: '1px solid var(--color-mist)', borderRadius: 10,
  padding: '8px 12px', fontSize: 13, cursor: 'pointer', color: 'var(--color-obsidian-ink)', font: 'inherit',
}
const primaryBtn: React.CSSProperties = {
  background: 'var(--color-voltage)', color: 'var(--voltage-on-dark)', border: 'none',
  borderRadius: 10, padding: '9px 14px', fontSize: 13, fontWeight: 500, cursor: 'pointer', font: 'inherit',
}
const ghostBtn: React.CSSProperties = {
  background: 'var(--color-linen)', border: '1px solid var(--color-mist)', borderRadius: 10,
  padding: '9px 14px', fontSize: 13, cursor: 'pointer', color: 'var(--color-obsidian-ink)', font: 'inherit',
}
```

- [ ] **Step 2: Montar la tarjeta en Agenda**

En `web-react/src/routes/Agenda.tsx`:
1. Agregar el import arriba (junto a los otros imports de componentes):
```tsx
import CalendarSubscribe from '../components/CalendarSubscribe'
```
2. En el JSX que devuelve `Agenda()`, montar `<CalendarSubscribe />` cerca del inicio del contenido (después del header de la pantalla, antes de la lista de eventos). Buscar el contenedor raíz del return y agregar como primer hijo del área de contenido:
```tsx
      <div style={{ padding: '0 18px 12px' }}>
        <CalendarSubscribe />
      </div>
```
(Ubicarlo de forma consistente con el padding/estructura existente de Agenda.tsx; si la pantalla ya tiene un `<section>` de header, ponerlo justo después.)

- [ ] **Step 3: Build (valida TS)**

Run:
```bash
cd web-react && npm run build
```
Expected: build OK, sin errores de TypeScript.

- [ ] **Step 4: Commit**

```bash
git add web-react/src/components/CalendarSubscribe.tsx web-react/src/routes/Agenda.tsx
git commit -m "feat(cal): tarjeta 'Suscribir a mi calendario' en Agenda"
```

---

## Task 5: Deploy frontend + verificación end-to-end

**Files:** ninguno (deploy + verificación).

- [ ] **Step 1: Subir el frontend a staging**

Run:
```bash
ssh emir@217.76.48.219 'rm -rf ~/asistente/webapp && mkdir -p ~/asistente/webapp'
scp -r web-react/dist/* emir@217.76.48.219:~/asistente/webapp/
```

- [ ] **Step 2: El usuario publica el frontend**

```bash
ssh -t emir@217.76.48.219 'sudo rm -rf /var/www/juntu && sudo cp -r ~/asistente/webapp /var/www/juntu && sudo chmod -R a+rX /var/www/juntu'
```

- [ ] **Step 3: Verificación end-to-end**

1. Abrir `https://asistente.emir-maestu.site/app/agenda` → tocar **"Suscribir a mi calendario"** → debe aparecer la URL.
2. Copiar la URL y abrirla en el navegador → debe descargar/mostrar un `.ics` que arranca con `BEGIN:VCALENDAR`.
3. (Opcional real) En Google Calendar → *Otros calendarios → Desde URL* → pegar → confirmar que aparecen los eventos/recordatorios propios.
4. Tocar **Regenerar** → la URL cambia y la anterior da 404 (`curl` la vieja).

- [ ] **Step 4: Actualizar CHANGELOG + commit final**

Agregar en `CHANGELOG.md` (sección `[Unreleased] / Added`):
```markdown
- **Calendario suscribible (.ics).** Cada usuario puede suscribir su Google/Apple/Outlook Calendar a un feed de Yumi (sus eventos + recordatorios). URL secreta y revocable, desde la pantalla Agenda. Es una vía (Yumi → calendario, solo lectura); se actualiza cada varias horas.
```
```bash
git add CHANGELOG.md && git commit -m "docs(changelog): feed de calendario .ics"
```

---

## Notas de cierre

- **No es tiempo real:** Google refresca el `.ics` cada varias horas (hasta ~24h). Es del protocolo; está aclarado en la UI.
- **Limpieza:** los `tests/` quedan en el repo (`vps_current/tests/`); en el VPS quedan copiados en `~/asistente/tests/` para correr pytest — no afectan al runtime.
- **Futuro (otro spec):** dos vías con OAuth de Google (crear eventos desde Google que vuelvan a Yumi) requiere verificación de Google.
