# Dashboard React — Core financiero (mobile-first)

**Fecha:** 2026-06-22
**Estado:** Diseño aprobado, pendiente de plan de implementación
**Sub-proyecto:** 1 de N (parte de la transformación a SaaS)

---

## 1. Contexto

El producto actual es un asistente personal (bot Telegram + dashboard web) para finanzas
de parejas/familias en Argentina. El backend es **FastAPI + SQLite** y ya expone ~50
endpoints REST limpios (`web.py`, `crud_v2.py`, `vencimientos.py`). El dashboard actual
es **HTML/JS vanilla embebido** (`dashboard.html`, 1.134 líneas) con el **mobile roto**.

Este sub-proyecto reemplaza ese dashboard por un **SPA React mobile-first** enfocado en el
**núcleo financiero**, con la estética editorial de NewForm adaptada a un producto de datos.
No se reescribe el backend.

### Decisiones ya tomadas (turnos previos)
- **Posicionamiento:** gestor de gastos para parejas argentinas, experto en tarjetas/cuotas/dólar.
- **Alcance del dashboard:** *core financiero primero*. Las vistas de productividad
  (hábitos/notas/tareas/eventos) NO se reconstruyen ahora; quedan accesibles en el dashboard
  viejo vía enlaces a `/legacy`.
- **Enfoque técnico:** Opción A — Vite + React SPA estático servido por Caddy, conviviendo con
  el dashboard viejo hasta hacer el "flip".
- **Número hero de la pantalla Inicio:** **Gasto del mes** (ancla de retención diaria).
  "Comprometido en cuotas" va como card destacada justo debajo.

---

## 2. Objetivos y no-objetivos

### Objetivos
1. Dashboard financiero **mobile-first**, usable en el celular (resuelve el mobile roto actual).
2. Estética NewForm adaptada (ver §4), reutilizable como base de marca.
3. **Cero cambios de runtime en el VPS** (build estático; sin Node corriendo en producción).
4. **Sin tocar el backend de auth**; reutiliza la cookie de sesión existente.
5. Dejar el terreno listo para meter el **paywall** después (base moderna y componible).

### No-objetivos (explícitos, para este sub-proyecto)
- Reconstruir hábitos / notas / tareas / eventos / recordatorios (quedan en `/legacy`).
- Modo oscuro (los tokens Obsidian existen; se hace después).
- Migración a WhatsApp, pricing/paywall, landing pública, nombre/branding (sub-proyectos aparte).
- Cambios de esquema de base de datos.

---

## 3. Arquitectura general

```
Navegador (SPA React)  ──fetch (credentials:include, same-origin)──►  Caddy
                                                                        ├─ /app/*  → estáticos dist/ (SPA fallback index.html)
                                                                        ├─ /        → dashboard viejo (hasta el flip)
                                                                        └─ /api/*, /login, /logout → uvicorn (FastAPI)
```

- **Mismo dominio** (`asistente.emir-maestu.site`) → **sin CORS**. La cookie `session`
  (httponly, secure, samesite=lax) viaja sola.
- El backend solo agrega: regla de Caddy para servir el SPA y el fallback de rutas.
- **Flip final:** React pasa a `/`, el viejo a `/legacy` (cambio de config de Caddy +
  `base` de Vite de `/app/` a `/`).

---

## 4. Sistema de diseño (NewForm adaptado a datos)

Origen: tokens extraídos de newformcap.com (`theme.css`, `variables.css`, `tokens.json`, `DESIGN.md`).

### Principio rector
Conservar el **alma** de NewForm (canvas Linen, tinta Obsidian, un único verde Voltage como
puntuación, número protagonista en serif, jerarquía por tipografía y no por chrome) y
**adaptarla a densidad de datos** (escala mobile con `clamp()`, hairlines Mist donde la
densidad lo pide, bottom-nav mínima que la referencia no tiene).

### Colores (uso)
- `--color-linen #fafffa` — canvas y superficies de card (las cards se definen por radio +
  padding + hairline, no por fill distinto).
- `--color-obsidian-ink #121613` — texto primario, marcos, barras de gráfico.
- `--color-sage #516254` — labels/captions y texto muteado.
- `--color-mist #c8d2c8` — hairlines y divisores.
- `--color-voltage #2bee4b` — **SOLO**: CTA principal (botón "+" con glow verde), estado de
  nav activa, píldoras de alerta (p. ej. "cierra en 3 días"), tick decorativo. Nunca en body,
  títulos ni fondos grandes.
- Texto sobre fondo Voltage: verde oscuro de la familia (`#0f3d18`), nunca negro puro.

### Tipografía (sustitutos libres)
Las fuentes originales (TWK Lausanne, Editorial New, PP Mondwest) son de pago. Se usan
equivalentes libres self-hosteados con `@fontsource`:
- **Inter** → UI, labels y body (pesos 350/400/500).
- **Fraunces** (peso 300, opsz alto) → número protagonista y display serif editorial.
- Escala display: `clamp()` para que el "masthead" (gasto del mes) sea grande en mobile sin
  romper el layout (~48–56px en mobile, mayor en desktop).

### Forma y elevación
- Radios: cards 14px, botones 10px, elementos chicos 5px (tokens del sistema).
- **Sin sombras** salvo el botón "+" (glow verde dual del CTA NewForm).
- Sin cards con borde pesado ni paneles rellenos: hairline Mist + padding + radio.

### Implementación
- Tailwind v4 con bloque `@theme` poblado desde `theme.css` (ya provisto).
- Tokens expuestos también como CSS custom properties para uso puntual fuera de utilidades.

---

## 5. Información y vistas (rutas)

### En la bottom-nav (uso diario)
| Ruta | Vista | Contenido | Endpoints |
|------|-------|-----------|-----------|
| `/` | **Inicio** | Hero "Gasto del mes" (+ comparativa vs mes pasado), stats (ingresos, disponible), **card de Cuotas/Vencimientos** (comprometido + próximos pagos), gastos por categoría, "hoy" (próximos pagos). | `GET /api/overview2` (trae gasto_mes, gasto_prev_alt, ingreso_mes, patrimonio, cuotas_futuras, cashflow, por_cat, hoy_items), `GET /api/vencimientos` |
| `/movimientos` | **Movimientos** | Lista de transacciones con filtros (período, cuenta, categoría, moneda), búsqueda, alta/edición/borrado, acciones masivas (bulk delete/move). | `GET/POST/PATCH/DELETE /api/transactions`, `POST /api/transactions/bulk_delete`, `POST /api/transactions/bulk_move`, `GET /api/categories`, `GET /api/accounts` |
| `/tarjetas` | **Tarjetas** (vista estrella) | Por tarjeta de crédito: cierre/vencimiento, cuotas activas, total comprometido, próximos pagos. Alerta antes del cierre. | `GET /api/vencimientos`, `GET /api/recurring`, `GET /api/accounts` (type=credito) |
| `/cuentas` | **Cuentas** | Saldos multi-moneda por cuenta, patrimonio neto, ABM de cuentas. | `GET /api/accounts`, `GET /api/overview`, `GET /api/networth` |
| `(+)` | **Alta rápida** (sheet/modal, no ruta full) | Form de alta de transacción con react-hook-form + zod. Guiño "también podés escribirle al bot". | `POST /api/transactions`, `GET /api/accounts`, `GET /api/categories` |

### En el menú (☰), fuera de la nav diaria
| Ruta | Vista | Endpoints |
|------|-------|-----------|
| `/categorias` | Categorías + Presupuestos | `GET/POST/PATCH/DELETE /api/categories`, `GET/POST/DELETE /api/budgets` |
| `/perfil` | Toggle scope (Mío/De Lisa/Ambos), cambio de password, logout, Export CSV | `GET /api/me`, `POST /api/set_scope`, `GET /api/export.csv`, `GET /logout` |
| (chip header) | Cotización del dólar | `GET /api/cotizacion` |
| `/legacy/*` | "Otras secciones": hábitos/notas/tareas/eventos del dashboard viejo (enlace externo) | dashboard viejo |

---

## 6. Navegación

- **Mobile:** top-bar (marca · toggle de scope · ☰) + bottom-nav de 5 (Inicio · Movimientos ·
  **[+]** central · Tarjetas · Cuentas). El "+" es el único elemento Voltage relleno (con glow).
- **Desktop (≥1024px):** misma app; la nav pasa a **sidebar izquierdo**. Contenido a ancho
  cómodo (~1100px) conservando el aire editorial. El "+" se vuelve botón en el sidebar/header.
- El menú ☰ abre un drawer con las secciones secundarias y el enlace a `/legacy`.

---

## 7. Stack técnico y flujo de datos

- **Build/runtime:** Vite + React + **TypeScript**. Node 20+ para build. Package manager: npm.
- **Estilos:** Tailwind v4 (`@theme` con tokens NewForm). Fuentes vía `@fontsource` (Inter, Fraunces).
- **Routing:** React Router (data router). `base` de Vite = `/app/` (cambia a `/` en el flip).
- **Server state:** **TanStack Query** sobre todos los endpoints (cache, refetch, loading/error).
- **Cliente API** (`lib/api.ts`): wrapper de `fetch` con `credentials:'include'`. 401 → redirect
  a `/login`. Mismo origen ⇒ sin CORS.
- **Auth:** reutiliza la cookie de sesión. La pantalla de login del SPA postea a `/login`
  (endpoint actual: devuelve JSON + setea cookie). Bootstrap con `GET /api/me`. El cliente
  `api.ts` **aísla la estrategia de auth** (cookie hoy) para poder pasar a token/bearer cuando
  exista la app nativa, cambiando un solo archivo (ver §11b).
- **Scope (Mío/Lisa/Ambos):** lo maneja el backend vía cookie `scope`. El toggle hace
  `POST /api/set_scope` y luego **invalida las queries** de TanStack Query para refrescar.
- **Forms:** react-hook-form + zod (alta/edición de transacción, cuentas, categorías, budgets).
- **Estado global:** mínimo. No se usa Redux.

### Formateo (reglas de datos)
- Moneda: `Intl.NumberFormat('es-AR')` → `$1.140.000` (ARS sin decimales; USD/EUR con 0–2 según contexto).
- Multi-moneda: cada cuenta puede tener saldos en ARS/USD/EUR; se muestran separados.
- Conversión a ARS para totales (patrimonio, comprometido) usando dólar blue (el backend ya
  la hace en `/api/overview2`; el front solo formatea y muestra "≈ US$ …").
- Fechas en formato local AR.

### Estados de UI (obligatorios por vista)
- **Loading:** skeletons sobrios (sin spinners ruidosos), respetando el canvas Linen.
- **Empty:** copy útil ("Todavía no cargaste gastos este mes — escribile al bot o tocá +").
- **Error:** mensaje claro + reintento; 401 → login.

---

## 8. Cambios en el backend (mínimos)

- **Caddy:** servir `dist/` en `/app` con fallback SPA (`try_files` → `index.html`); seguir
  proxeando `/api`, `/login`, `/logout` a uvicorn.
- Posible afinado de 1–2 *shapes* de respuesta si durante el armado falta algún campo
  (se documenta y se hace puntual; no es un objetivo rediseñar la API).
- No se tocan auth, esquema de DB ni lógica del bot.

---

## 9. Estructura de carpetas (nueva, separada del Python)

```
web-react/
  index.html
  vite.config.ts          (base '/app/', proxy /api → FastAPI en dev)
  package.json
  src/
    main.tsx
    App.tsx               (router + providers)
    lib/
      api.ts              (fetch client, manejo 401)
      format.ts          (moneda/fechas AR, conversión USD)
    hooks/                (useOverview, useTransactions, useVencimientos, useAccounts, ...)
    components/
      ui/                 (Card, StatNumber, TickMark, MoneyText, Skeleton, Sheet, ...)
      nav/                (TopBar, BottomNav, Sidebar, ScopeToggle, MenuDrawer)
    routes/               (Inicio, Movimientos, Tarjetas, Cuentas, Categorias, Perfil, Login)
    styles/
      theme.css           (tokens NewForm + @theme Tailwind)
```

---

## 10. Testing (liviano, fundador solo)

Vitest + React Testing Library, enfocado en lo que duele si se rompe:
- `format.ts`: moneda AR (`$1.140.000`, miles con punto), conversión USD/blue, fechas.
- Filtros de **Movimientos** (período/cuenta/categoría/moneda).
- Render de **Inicio** con datos mockeados (hero = gasto del mes; card de cuotas).

No se busca coverage exhaustivo.

---

## 11. Riesgos y preguntas abiertas

- **Marca/nombre:** `[ tu marca ]` es placeholder; el logo replicará el split Obsidian/Voltage
  cuando definamos el nombre (sub-proyecto aparte). No bloquea este trabajo.
- **Licencias de fuentes:** resuelto usando sustitutos libres (Inter/Fraunces).
- **Paridad de datos legacy:** mientras hábitos/notas/tareas vivan en `/legacy`, la navegación
  entre apps debe sentirse fluida (mismo dominio, misma sesión). Aceptable como interino.
- **Dev loop sin git:** el proyecto no es un repo git hoy. Recomendado `git init` antes de
  empezar a implementar para tener historial y poder revertir.
- **El backend es la fuente de verdad de scope/conversión:** el front no recalcula; si un total
  parece mal, se corrige en el endpoint, no en React.

---

## 11b. Compatibilidad futura: app nativa (Android/iOS)

Requerimiento a futuro (no en este sub-proyecto): publicar app nativa en App Store / Play Store.

**Camino elegido:** React web ahora → **Capacitor** después. Capacitor empaqueta el mismo
build React en un caparazón nativo, reutilizando ~95% del código. Alternativas descartadas para
hoy: React Native/Expo (codebase separada, duplicaría el trabajo) y PWA-only (sin tiendas, push
limitado en iOS; sirve como escalón intermedio opcional).

**Qué cuidar desde hoy para que el salto sea barato (decisiones de este sub-proyecto):**
- **Auth swappable:** toda la lógica de credenciales vive en `lib/api.ts`. En Capacitor el
  origen cambia y la cookie httponly same-site no viaja igual → habrá que pasar a token/bearer.
  Diseñar `api.ts` para que ese cambio sea de un solo archivo (el backend podría sumar emisión
  de token además de la cookie, sin romper la web).
- **Rutas relativas y `base` configurable:** ya contemplado (`/app/` → `/`); para Capacitor el
  `base` puede ser relativo.
- **APIs web-only con fallback:** evitar dependencias de DOM/Web que no existan en WebView; las
  capacidades nativas (push, cámara/OCR, biometría) entran como plugins de Capacitor más adelante.
- **Mobile-first táctil:** ya es el default del diseño; targets táctiles y gestos amigables.

No se implementa Capacitor en este sub-proyecto; solo se preservan estas puertas abiertas.

## 12. Fuera de alcance / próximos sub-proyectos
Pricing + paywall (MercadoPago), login/onboarding comercial, landing pública, nombre/branding,
WhatsApp, modo oscuro, migración de vistas de productividad a React, **app nativa con Capacitor
(ver §11b)**.
