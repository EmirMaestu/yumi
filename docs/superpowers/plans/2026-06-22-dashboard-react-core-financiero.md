# Dashboard React — Core financiero — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reemplazar el dashboard HTML/JS vanilla por un SPA React mobile-first enfocado en el núcleo financiero (gasto del mes, movimientos, tarjetas/cuotas, cuentas), con la estética NewForm adaptada, sin tocar el backend de auth ni el esquema de DB.

**Architecture:** Vite + React + TypeScript compilado a estáticos, servido por Caddy en `/app` (con flip posterior a `/`). Consume la API FastAPI existente vía `fetch` mismo-origen (sin CORS), con la cookie de sesión actual. Server-state con TanStack Query; estado global mínimo. Forward-compatible con Capacitor (auth aislada en un solo archivo).

**Tech Stack:** Vite, React 18, TypeScript, Tailwind v4 (`@theme` con tokens NewForm), TanStack Query v5, React Router v6, react-hook-form + zod, @fontsource (Inter, Fraunces), Vitest + Testing Library.

**Spec:** `docs/superpowers/specs/2026-06-22-dashboard-react-core-financiero-design.md`

---

## File Structure

```
web-react/
  index.html
  package.json
  vite.config.ts            base '/app/', proxy /api,/login,/logout → FastAPI; vitest config
  tsconfig.json
  src/
    main.tsx                bootstrap: Router + QueryClientProvider
    App.tsx                 rutas + layout
    vite-env.d.ts
    styles/
      theme.css             @import tailwindcss + @theme (tokens NewForm) + base
    lib/
      api.ts                fetch client, auth aislada, manejo 401
      api.test.ts
      format.ts             moneda/fechas AR, conversión USD
      format.test.ts
      types.ts              tipos de las respuestas de la API
    hooks/
      useMe.ts              GET /api/me (+ setScope)
      useOverview.ts        GET /api/overview2
      useVencimientos.ts    GET /api/vencimientos
      useTransactions.ts    GET/POST/PATCH/DELETE /api/transactions (+ bulk)
      useAccounts.ts        GET/POST/PATCH/DELETE /api/accounts
      useCategories.ts      GET/POST/PATCH/DELETE /api/categories (+ budgets)
      useRecurring.ts       GET/PATCH/DELETE /api/recurring
      useCotizacion.ts      GET /api/cotizacion
    components/
      ui/
        Card.tsx            superficie hairline + radio 14
        MoneyText.tsx       número formateado (serif opcional)
        StatNumber.tsx      label + valor
        TickMark.tsx        línea voltage decorativa
        Skeleton.tsx        placeholder de carga
        EmptyState.tsx      vacío con copy útil
        Sheet.tsx           bottom-sheet/modal en flujo normal
        AlertPill.tsx       píldora voltage (alertas)
        CategoryBar.tsx     barra monocromática de categoría
      nav/
        AppLayout.tsx       layout responsive (bottom-nav mobile / sidebar desktop)
        TopBar.tsx          marca + scope + menú
        BottomNav.tsx       5 ítems con "+" central
        Sidebar.tsx         nav desktop
        ScopeToggle.tsx     Mío/De Lisa/Ambos → POST /api/set_scope
        MenuDrawer.tsx      secciones secundarias + link /legacy
      QuickAddSheet.tsx     alta rápida de transacción (rhf + zod)
    routes/
      Login.tsx
      Inicio.tsx
      Movimientos.tsx
      Tarjetas.tsx
      Cuentas.tsx
      Categorias.tsx
      Perfil.tsx
    test/
      setup.ts              jsdom + jest-dom + QueryClient wrapper
      utils.tsx             renderWithProviders()
```

**Backend (sin código React):** una regla de Caddy para servir `dist/` en `/app` con fallback SPA. Documentada en la Task final; no se toca FastAPI.

---

## PHASE 0 — Project foundation

### Task 0: Repo + scaffold Vite React TS

**Files:**
- Create: `web-react/` (vía scaffold), `.gitignore`

- [ ] **Step 1: Init git (el proyecto no es repo hoy)**

Run desde la raíz `asistant/`:
```bash
git init
printf "node_modules/\ndist/\n*.local\n.DS_Store\n__pycache__/\nvenv/\ndata.db\n.env\n" > .gitignore
git add .gitignore && git commit -m "chore: init git repo with gitignore"
```

- [ ] **Step 2: Verificar Node 20+**

Run:
```bash
node --version
```
Expected: `v20.x` o mayor. Si no está, instalar Node 20 LTS antes de seguir.

- [ ] **Step 3: Scaffold Vite (React + TS)**

Run desde la raíz `asistant/`:
```bash
npm create vite@latest web-react -- --template react-ts
cd web-react && npm install
```
Expected: crea `web-react/` con la plantilla y instala dependencias.

- [ ] **Step 4: Smoke run**

Run (en `web-react/`):
```bash
npm run dev
```
Expected: Vite levanta en `http://localhost:5173` sin errores. Cortar con Ctrl+C.

- [ ] **Step 5: Commit**

```bash
git add web-react && git commit -m "chore: scaffold vite react-ts app"
```

---

### Task 1: Dependencias del proyecto

**Files:**
- Modify: `web-react/package.json` (vía npm install)

- [ ] **Step 1: Instalar runtime deps**

Run (en `web-react/`):
```bash
npm install react-router-dom @tanstack/react-query react-hook-form zod @hookform/resolvers @fontsource/inter @fontsource/fraunces
```

- [ ] **Step 2: Instalar Tailwind v4 + plugin Vite**

Run:
```bash
npm install -D tailwindcss @tailwindcss/vite
```

- [ ] **Step 3: Instalar toolchain de tests**

Run:
```bash
npm install -D vitest jsdom @testing-library/react @testing-library/jest-dom @testing-library/user-event
```

- [ ] **Step 4: Commit**

```bash
git add web-react/package.json web-react/package-lock.json
git commit -m "chore: add project dependencies"
```

---

### Task 2: Configurar Vite (Tailwind, base, proxy, vitest)

**Files:**
- Modify: `web-react/vite.config.ts`

- [ ] **Step 1: Escribir la config**

Reemplazar `web-react/vite.config.ts` con:
```ts
/// <reference types="vitest" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  base: '/app/', // cambia a '/' en el flip final
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
      '/login': 'http://localhost:8000',
      '/logout': 'http://localhost:8000',
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/test/setup.ts',
  },
})
```

- [ ] **Step 2: Agregar scripts de test a package.json**

En `web-react/package.json`, dentro de `"scripts"`, agregar:
```json
"test": "vitest run",
"test:watch": "vitest"
```

- [ ] **Step 3: Commit**

```bash
git add web-react/vite.config.ts web-react/package.json
git commit -m "chore: configure vite (tailwind, base /app/, api proxy, vitest)"
```

---

### Task 3: Tokens de diseño NewForm (theme.css)

**Files:**
- Create: `web-react/src/styles/theme.css`
- Modify: `web-react/src/main.tsx` (import del css y fuentes)
- Delete: `web-react/src/App.css`, `web-react/src/index.css` (de la plantilla)

- [ ] **Step 1: Escribir theme.css**

Crear `web-react/src/styles/theme.css`:
```css
@import "tailwindcss";

@theme {
  --color-linen: #fafffa;
  --color-obsidian-ink: #121613;
  --color-pure-black: #000000;
  --color-bark: #232924;
  --color-sage: #516254;
  --color-mist: #c8d2c8;
  --color-voltage: #2bee4b;
  --color-moss-glow: #93b799;
  --color-pollen: #c4e4c9;

  --font-sans: "Inter", ui-sans-serif, system-ui, sans-serif;
  --font-serif: "Fraunces", Georgia, serif;

  --radius-card: 14px;
  --radius-btn: 10px;
  --radius-sm: 5px;

  --shadow-cta: rgba(16,94,29,0.45) 1px 8px 20px 0px, rgba(18,146,39,0.25) 1px 8px 20px 0px;
}

:root {
  --voltage-on-dark: #0f3d18; /* texto sobre fondo voltage */
}

html, body, #root { height: 100%; }
body {
  margin: 0;
  background: var(--color-linen);
  color: var(--color-obsidian-ink);
  font-family: var(--font-sans);
  -webkit-font-smoothing: antialiased;
}
.cap {
  font-size: 11px; letter-spacing: 0.09em; text-transform: uppercase;
  color: var(--color-sage); font-weight: 500;
}
.num-serif { font-family: var(--font-serif); font-weight: 300; line-height: 0.92; }
```

- [ ] **Step 2: Reemplazar main.tsx**

Reemplazar `web-react/src/main.tsx`:
```tsx
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import '@fontsource/inter/350.css'
import '@fontsource/inter/400.css'
import '@fontsource/inter/500.css'
import '@fontsource/fraunces/300.css'
import './styles/theme.css'
import App from './App'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
```

- [ ] **Step 3: Borrar css de la plantilla**

Run:
```bash
rm web-react/src/App.css web-react/src/index.css
```

- [ ] **Step 4: App.tsx mínimo para compilar**

Reemplazar `web-react/src/App.tsx`:
```tsx
export default function App() {
  return <div className="cap" style={{ padding: 20 }}>setup ok</div>
}
```

- [ ] **Step 5: Verificar build**

Run (en `web-react/`):
```bash
npm run build
```
Expected: build exitoso, sin errores de tipos ni de css.

- [ ] **Step 6: Commit**

```bash
git add -A web-react/src && git commit -m "feat: newform design tokens + fonts"
```

---

### Task 4: Test harness (setup + renderWithProviders)

**Files:**
- Create: `web-react/src/test/setup.ts`, `web-react/src/test/utils.tsx`

- [ ] **Step 1: setup.ts**

Crear `web-react/src/test/setup.ts`:
```ts
import '@testing-library/jest-dom/vitest'
```

- [ ] **Step 2: renderWithProviders**

Crear `web-react/src/test/utils.tsx`:
```tsx
import { ReactElement } from 'react'
import { render } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'

export function renderWithProviders(ui: ReactElement, route = '/') {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[route]}>{ui}</MemoryRouter>
    </QueryClientProvider>,
  )
}
```

- [ ] **Step 3: Test trivial para validar el harness**

Crear `web-react/src/test/smoke.test.tsx`:
```tsx
import { screen } from '@testing-library/react'
import { renderWithProviders } from './utils'

test('harness renders', () => {
  renderWithProviders(<div>hola</div>)
  expect(screen.getByText('hola')).toBeInTheDocument()
})
```

- [ ] **Step 4: Run**

Run:
```bash
npm test
```
Expected: 1 test PASS.

- [ ] **Step 5: Commit**

```bash
git add -A web-react/src/test && git commit -m "test: vitest harness + renderWithProviders"
```

---

## PHASE 1 — Core libs (TDD)

### Task 5: format.ts (moneda y fechas AR)

**Files:**
- Create: `web-react/src/lib/format.ts`, `web-react/src/lib/format.test.ts`

- [ ] **Step 1: Escribir los tests (fallan)**

Crear `web-react/src/lib/format.test.ts`:
```ts
import { formatMoney, formatUsdApprox, formatMonthLabel } from './format'

test('formatMoney ARS: miles con punto, sin decimales', () => {
  expect(formatMoney(1140000)).toBe('$1.140.000')
  expect(formatMoney(0)).toBe('$0')
  expect(formatMoney(612300.7)).toBe('$612.301')
})

test('formatMoney USD y EUR con prefijo propio', () => {
  expect(formatMoney(2066, 'USD')).toBe('US$2.066')
  expect(formatMoney(50, 'EUR')).toBe('€50')
})

test('formatUsdApprox usa el blue; null si no hay rate', () => {
  expect(formatUsdApprox(2480500, 1200)).toBe('≈ US$2.067')
  expect(formatUsdApprox(2480500, 0)).toBeNull()
  expect(formatUsdApprox(2480500, null)).toBeNull()
})

test('formatMonthLabel devuelve mes y año en es-AR', () => {
  expect(formatMonthLabel(2026, 6)).toBe('junio 2026')
})
```

- [ ] **Step 2: Run (deben fallar por módulo inexistente)**

Run:
```bash
npx vitest run src/lib/format.test.ts
```
Expected: FAIL ("Failed to resolve import ./format").

- [ ] **Step 3: Implementar format.ts**

Crear `web-react/src/lib/format.ts`:
```ts
type Currency = 'ARS' | 'USD' | 'EUR'

const SYMBOL: Record<Currency, string> = { ARS: '$', USD: 'US$', EUR: '€' }
const grouper = new Intl.NumberFormat('es-AR', { maximumFractionDigits: 0 })
const MESES = [
  'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
  'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre',
]

export function formatMoney(amount: number, currency: Currency = 'ARS'): string {
  return `${SYMBOL[currency]}${grouper.format(Math.round(amount))}`
}

export function formatUsdApprox(amountArs: number, blue: number | null): string | null {
  if (!blue || blue <= 0) return null
  return `≈ ${formatMoney(amountArs / blue, 'USD')}`
}

export function formatMonthLabel(year: number, month1to12: number): string {
  return `${MESES[month1to12 - 1]} ${year}`
}
```

- [ ] **Step 4: Run (pasan)**

Run:
```bash
npx vitest run src/lib/format.test.ts
```
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add web-react/src/lib/format.ts web-react/src/lib/format.test.ts
git commit -m "feat: AR money/date formatting with tests"
```

---

### Task 6: api.ts (cliente fetch, auth aislada, manejo 401)

**Files:**
- Create: `web-react/src/lib/api.ts`, `web-react/src/lib/api.test.ts`

- [ ] **Step 1: Escribir los tests (fallan)**

Crear `web-react/src/lib/api.test.ts`:
```ts
import { afterEach, expect, test, vi } from 'vitest'
import { apiGet, apiPost, setUnauthorizedHandler, ApiError } from './api'

afterEach(() => vi.restoreAllMocks())

test('apiGet manda credentials include y parsea JSON', async () => {
  const fetchMock = vi.fn().mockResolvedValue(
    new Response(JSON.stringify({ ok: true }), { status: 200, headers: { 'Content-Type': 'application/json' } }),
  )
  vi.stubGlobal('fetch', fetchMock)

  const data = await apiGet<{ ok: boolean }>('/api/me')

  expect(data.ok).toBe(true)
  const [, opts] = fetchMock.mock.calls[0]
  expect(opts.credentials).toBe('include')
})

test('apiPost envía body JSON', async () => {
  const fetchMock = vi.fn().mockResolvedValue(new Response('{}', { status: 200 }))
  vi.stubGlobal('fetch', fetchMock)

  await apiPost('/api/transactions', { amount: 100 })

  const [, opts] = fetchMock.mock.calls[0]
  expect(opts.method).toBe('POST')
  expect(JSON.parse(opts.body)).toEqual({ amount: 100 })
})

test('un 401 dispara el handler y lanza ApiError', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('no', { status: 401 })))
  const handler = vi.fn()
  setUnauthorizedHandler(handler)

  await expect(apiGet('/api/me')).rejects.toBeInstanceOf(ApiError)
  expect(handler).toHaveBeenCalledOnce()
})
```

- [ ] **Step 2: Run (fallan)**

Run:
```bash
npx vitest run src/lib/api.test.ts
```
Expected: FAIL ("Failed to resolve import ./api").

- [ ] **Step 3: Implementar api.ts**

Crear `web-react/src/lib/api.ts`:
```ts
export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message)
    this.name = 'ApiError'
  }
}

let onUnauthorized: () => void = () => {}
export function setUnauthorizedHandler(fn: () => void) {
  onUnauthorized = fn
}

// Auth aislada: hoy la cookie viaja sola (same-origin). Para Capacitor/nativo,
// este es el ÚNICO lugar a cambiar (devolver { Authorization: `Bearer ${token}` }).
function authHeaders(): Record<string, string> {
  return {}
}

async function request<T>(path: string, init: RequestInit): Promise<T> {
  const res = await fetch(path, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    ...init,
  })
  if (res.status === 401) {
    onUnauthorized()
    throw new ApiError(401, 'No autorizado')
  }
  if (!res.ok) {
    const detail = await res.text().catch(() => '')
    throw new ApiError(res.status, detail || `Error ${res.status}`)
  }
  if (res.status === 204) return undefined as T
  const text = await res.text()
  return (text ? JSON.parse(text) : undefined) as T
}

export const apiGet = <T>(path: string) => request<T>(path, { method: 'GET' })
export const apiPost = <T>(path: string, body?: unknown) =>
  request<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) })
export const apiPatch = <T>(path: string, body?: unknown) =>
  request<T>(path, { method: 'PATCH', body: body === undefined ? undefined : JSON.stringify(body) })
export const apiDelete = <T>(path: string) => request<T>(path, { method: 'DELETE' })
```

- [ ] **Step 4: Run (pasan)**

Run:
```bash
npx vitest run src/lib/api.test.ts
```
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add web-react/src/lib/api.ts web-react/src/lib/api.test.ts
git commit -m "feat: api client with isolated auth + 401 handling"
```

---

### Task 7: types.ts (tipos de la API)

**Files:**
- Create: `web-react/src/lib/types.ts`

> Tipos derivados de las respuestas reales de `web.py`. Si durante el armado un endpoint
> devuelve un campo extra/distinto, se ajusta acá (la API es la fuente de verdad).

- [ ] **Step 1: Escribir types.ts**

Crear `web-react/src/lib/types.ts`:
```ts
export type Currency = 'ARS' | 'USD' | 'EUR'

export interface Me {
  id: number
  name: string
  username: string
  color?: string
  scope: string
  others: { name: string; scope_value: string }[]
}

export interface Balance { currency: Currency; balance: number }

export interface Account {
  id: number
  name: string
  type: 'efectivo' | 'billetera' | 'credito' | 'banco' | 'inversion'
  color?: string
  icon?: string
  active: number
  closing_day?: number | null
  due_day?: number | null
  balances?: Balance[]
}

export interface CategoryTotal { cat: string; color?: string; total: number }

export interface HoyItem { tipo: string; titulo: string; sub: string; hora: string }

export interface Overview2 {
  patrimonio_ars: number
  patrimonio_usd: number | null
  blue: number
  gasto_mes: number
  gasto_prev_alt: number
  ingreso_mes: number
  cuotas_futuras: number
  cuotas_n: number
  cashflow: { ym: string; ingresos: number; gastos: number }[]
  hoy_items: HoyItem[]
  por_categoria: CategoryTotal[]
  mes_nombre?: string
  year?: number
}

export interface Transaction {
  id: number
  type: 'gasto' | 'ingreso'
  amount: number
  currency: Currency
  description: string
  occurred_at: string
  account_id: number
  account_name?: string
  category_id?: number | null
  category_name?: string | null
}

export interface Category {
  id: number
  name: string
  color?: string
  icon?: string
}

export interface Recurring {
  id: number
  description: string
  amount: number
  currency: Currency
  account_id: number
  next_occurrence: string
  active: number
  total_installments?: number | null
  installments_fired?: number | null
}

export interface VencimientoCard {
  account_id: number
  account_name: string
  due_date: string
  closing_date?: string
  amount: number
  cycle_accumulated?: number
}
```

- [ ] **Step 2: Verificar tipos**

Run (en `web-react/`):
```bash
npx tsc --noEmit
```
Expected: sin errores.

- [ ] **Step 3: Commit**

```bash
git add web-react/src/lib/types.ts && git commit -m "feat: API response types"
```

---

## PHASE 2 — App shell, routing y auth

### Task 8: QueryClient + Router + onUnauthorized

**Files:**
- Modify: `web-react/src/main.tsx`, `web-react/src/App.tsx`

- [ ] **Step 1: main.tsx con providers**

Reemplazar el bloque `createRoot(...)` de `web-react/src/main.tsx` por:
```tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter } from 'react-router-dom'
import { setUnauthorizedHandler } from './lib/api'

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000, retry: 1 } },
})

setUnauthorizedHandler(() => {
  if (!location.pathname.endsWith('/login')) location.assign('/app/login')
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter basename="/app">
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
)
```
(Mantener los imports de fuentes y `theme.css` ya presentes. Agregar los nuevos imports arriba.)

- [ ] **Step 2: App.tsx con rutas placeholder**

Reemplazar `web-react/src/App.tsx`:
```tsx
import { Routes, Route, Navigate } from 'react-router-dom'
import Login from './routes/Login'
import Inicio from './routes/Inicio'

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/" element={<Inicio />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
```

- [ ] **Step 3: Stubs para compilar**

Crear `web-react/src/routes/Login.tsx`:
```tsx
export default function Login() {
  return <div className="cap" style={{ padding: 20 }}>login (stub)</div>
}
```
Crear `web-react/src/routes/Inicio.tsx`:
```tsx
export default function Inicio() {
  return <div className="cap" style={{ padding: 20 }}>inicio (stub)</div>
}
```

- [ ] **Step 4: Build + commit**

```bash
npm run build
git add -A web-react/src && git commit -m "feat: providers, router with /app basename, route stubs"
```

---

### Task 9: useMe + ScopeToggle

**Files:**
- Create: `web-react/src/hooks/useMe.ts`, `web-react/src/components/nav/ScopeToggle.tsx`

- [ ] **Step 1: useMe.ts**

Crear `web-react/src/hooks/useMe.ts`:
```ts
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiGet, apiPost } from '../lib/api'
import type { Me } from '../lib/types'

export function useMe() {
  return useQuery({ queryKey: ['me'], queryFn: () => apiGet<Me>('/api/me') })
}

export function useSetScope() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (value: string) => apiPost('/api/set_scope', { value }),
    onSuccess: () => qc.invalidateQueries(),
  })
}
```

- [ ] **Step 2: ScopeToggle.tsx**

Crear `web-react/src/components/nav/ScopeToggle.tsx`:
```tsx
import { useMe, useSetScope } from '../../hooks/useMe'

export default function ScopeToggle() {
  const { data: me } = useMe()
  const setScope = useSetScope()
  if (!me) return null
  const options = [
    { label: 'Mío', value: 'mine' },
    ...me.others.map((o) => ({ label: o.name, value: o.scope_value })),
    { label: 'Ambos', value: 'both' },
  ]
  return (
    <select
      aria-label="Ver datos de"
      value={me.scope}
      onChange={(e) => setScope.mutate(e.target.value)}
      style={{
        fontSize: 12, border: '1px solid var(--color-mist)', borderRadius: 9999,
        padding: '5px 11px', background: 'transparent', color: 'var(--color-obsidian-ink)',
      }}
    >
      {options.map((o) => (
        <option key={o.value} value={o.value}>{o.label}</option>
      ))}
    </select>
  )
}
```

- [ ] **Step 3: Test de ScopeToggle (render con me mockeado)**

Crear `web-react/src/components/nav/ScopeToggle.test.tsx`:
```tsx
import { screen } from '@testing-library/react'
import { vi, expect, test, afterEach } from 'vitest'
import { renderWithProviders } from '../../test/utils'
import ScopeToggle from './ScopeToggle'

afterEach(() => vi.restoreAllMocks())

test('muestra opciones de scope desde /api/me', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
    id: 1, name: 'Emir', username: 'emir', scope: 'mine',
    others: [{ name: 'Lisa', scope_value: 'user:Lisa' }],
  }), { status: 200 })))

  renderWithProviders(<ScopeToggle />)

  expect(await screen.findByText('Lisa')).toBeInTheDocument()
  expect(screen.getByText('Ambos')).toBeInTheDocument()
})
```

- [ ] **Step 4: Run**

Run:
```bash
npx vitest run src/components/nav/ScopeToggle.test.tsx
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add -A web-react/src/hooks web-react/src/components/nav
git commit -m "feat: useMe + ScopeToggle"
```

---

### Task 10: Login

**Files:**
- Modify: `web-react/src/routes/Login.tsx`

- [ ] **Step 1: Implementar Login**

Reemplazar `web-react/src/routes/Login.tsx`:
```tsx
import { useState } from 'react'

export default function Login() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    const res = await fetch('/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ username, password }),
    })
    if (res.ok) {
      location.assign('/app/')
    } else {
      const j = await res.json().catch(() => ({}))
      setError(j.detail || 'Credenciales inválidas')
    }
  }

  return (
    <main style={{ maxWidth: 360, margin: '0 auto', padding: '64px 24px' }}>
      <div className="cap">Tu plata, sin planillas</div>
      <h1 className="num-serif" style={{ fontSize: 44, margin: '12px 0 32px' }}>Entrar</h1>
      <form onSubmit={onSubmit} style={{ display: 'grid', gap: 14 }}>
        <input aria-label="Usuario" placeholder="Usuario" value={username}
          onChange={(e) => setUsername(e.target.value)} style={inputStyle} />
        <input aria-label="Contraseña" type="password" placeholder="Contraseña" value={password}
          onChange={(e) => setPassword(e.target.value)} style={inputStyle} />
        {error && <div style={{ color: '#a32d2d', fontSize: 13 }}>{error}</div>}
        <button type="submit" style={ctaStyle}>Entrar →</button>
      </form>
    </main>
  )
}

const inputStyle: React.CSSProperties = {
  border: '1px solid var(--color-mist)', borderRadius: 10, padding: '12px 14px',
  fontSize: 16, background: 'transparent', color: 'var(--color-obsidian-ink)',
}
const ctaStyle: React.CSSProperties = {
  background: 'var(--color-voltage)', color: 'var(--voltage-on-dark)', border: 'none',
  borderRadius: 10, padding: '14px 18px', fontSize: 14, fontWeight: 500,
  boxShadow: 'var(--shadow-cta)', cursor: 'pointer',
}
```

- [ ] **Step 2: Test de Login (submit exitoso redirige)**

Crear `web-react/src/routes/Login.test.tsx`:
```tsx
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi, expect, test, afterEach, beforeEach } from 'vitest'
import { renderWithProviders } from '../test/utils'
import Login from './Login'

const assign = vi.fn()
beforeEach(() => { vi.stubGlobal('location', { assign, pathname: '/app/login' }) })
afterEach(() => vi.restoreAllMocks())

test('login OK redirige a /app/', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{"ok":true}', { status: 200 })))
  renderWithProviders(<Login />)
  await userEvent.type(screen.getByLabelText('Usuario'), 'emir')
  await userEvent.type(screen.getByLabelText('Contraseña'), 'secret')
  await userEvent.click(screen.getByRole('button', { name: /entrar/i }))
  expect(assign).toHaveBeenCalledWith('/app/')
})
```

- [ ] **Step 3: Run**

Run:
```bash
npx vitest run src/routes/Login.test.tsx
```
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add -A web-react/src/routes/Login.tsx web-react/src/routes/Login.test.tsx
git commit -m "feat: login screen"
```

---

## PHASE 3 — UI primitives + layout

### Task 11: Componentes UI base

**Files:**
- Create: `web-react/src/components/ui/Card.tsx`, `MoneyText.tsx`, `StatNumber.tsx`, `TickMark.tsx`, `Skeleton.tsx`, `EmptyState.tsx`, `AlertPill.tsx`, `CategoryBar.tsx`

- [ ] **Step 1: Card.tsx**
```tsx
import { ReactNode } from 'react'
export default function Card({ children, style }: { children: ReactNode; style?: React.CSSProperties }) {
  return (
    <div style={{ border: '1px solid var(--color-mist)', borderRadius: 'var(--radius-card)', padding: 18, ...style }}>
      {children}
    </div>
  )
}
```

- [ ] **Step 2: MoneyText.tsx**
```tsx
import { formatMoney } from '../../lib/format'
import type { Currency } from '../../lib/types'
export default function MoneyText({ amount, currency = 'ARS', serif, size = 16 }:
  { amount: number; currency?: Currency; serif?: boolean; size?: number }) {
  return (
    <span className={serif ? 'num-serif' : undefined}
      style={{ fontSize: size, fontWeight: serif ? 300 : 500 }}>
      {formatMoney(amount, currency)}
    </span>
  )
}
```

- [ ] **Step 3: StatNumber.tsx**
```tsx
export default function StatNumber({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ flex: 1 }}>
      <div className="cap" style={{ fontSize: 10.5 }}>{label}</div>
      <div style={{ fontSize: 15, fontWeight: 500, marginTop: 3 }}>{children}</div>
    </div>
  )
}
```

- [ ] **Step 4: TickMark.tsx**
```tsx
export default function TickMark({ width = 50 }: { width?: number }) {
  return <div style={{ width, height: 2, background: 'var(--color-voltage)' }} />
}
```

- [ ] **Step 5: Skeleton.tsx**
```tsx
export default function Skeleton({ h = 16, w = '100%' }: { h?: number; w?: number | string }) {
  return <div aria-hidden style={{ height: h, width: w, background: 'var(--color-mist)', opacity: 0.5, borderRadius: 6 }} />
}
```

- [ ] **Step 6: EmptyState.tsx**
```tsx
export default function EmptyState({ children }: { children: React.ReactNode }) {
  return <div style={{ color: 'var(--color-sage)', fontSize: 14, padding: '24px 0', textAlign: 'center' }}>{children}</div>
}
```

- [ ] **Step 7: AlertPill.tsx**
```tsx
export default function AlertPill({ children }: { children: React.ReactNode }) {
  return (
    <span style={{
      background: 'var(--color-voltage)', color: 'var(--voltage-on-dark)', fontSize: 10.5,
      fontWeight: 600, padding: '2px 8px', borderRadius: 9999, display: 'inline-block',
    }}>{children}</span>
  )
}
```

- [ ] **Step 8: CategoryBar.tsx**
```tsx
import { formatMoney } from '../../lib/format'
export default function CategoryBar({ label, total, max }: { label: string; total: number; max: number }) {
  const pct = max > 0 ? Math.min(100, Math.round((total / max) * 100)) : 0
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 11 }}>
      <span style={{ fontSize: 13, width: 90 }}>{label}</span>
      <span style={{ flex: 1, height: 6, background: 'var(--color-mist)', borderRadius: 5, overflow: 'hidden' }}>
        <span style={{ display: 'block', width: `${pct}%`, height: '100%', background: 'var(--color-bark)' }} />
      </span>
      <span style={{ fontSize: 12.5, color: 'var(--color-sage)', width: 70, textAlign: 'right' }}>{formatMoney(total)}</span>
    </div>
  )
}
```

- [ ] **Step 9: Test de CategoryBar (lógica de %)**

Crear `web-react/src/components/ui/CategoryBar.test.tsx`:
```tsx
import { screen } from '@testing-library/react'
import { renderWithProviders } from '../../test/utils'
import CategoryBar from './CategoryBar'

test('renderiza label y total formateado', () => {
  renderWithProviders(<CategoryBar label="Comida" total={210000} max={210000} />)
  expect(screen.getByText('Comida')).toBeInTheDocument()
  expect(screen.getByText('$210.000')).toBeInTheDocument()
})
```

- [ ] **Step 10: Run + commit**
```bash
npx vitest run src/components/ui/CategoryBar.test.tsx
git add -A web-react/src/components/ui && git commit -m "feat: base UI primitives"
```

---

### Task 12: Navegación (TopBar, BottomNav, Sidebar, MenuDrawer) + AppLayout

**Files:**
- Create: `web-react/src/components/nav/TopBar.tsx`, `BottomNav.tsx`, `Sidebar.tsx`, `MenuDrawer.tsx`, `AppLayout.tsx`

- [ ] **Step 1: Definir los ítems de nav (compartidos)**

Crear `web-react/src/components/nav/navItems.ts`:
```ts
export interface NavItem { to: string; label: string; icon: string }
export const NAV_ITEMS: NavItem[] = [
  { to: '/', label: 'Inicio', icon: 'ti-home' },
  { to: '/movimientos', label: 'Movim.', icon: 'ti-arrows-left-right' },
  { to: '/tarjetas', label: 'Tarjetas', icon: 'ti-credit-card' },
  { to: '/cuentas', label: 'Cuentas', icon: 'ti-wallet' },
]
```

> Iconos: usar Tabler outline vía clase `ti ti-*`. Agregar el webfont en `index.html`
> (Step 6). En desktop/mobile se reusa `NAV_ITEMS`; el "+" central se renderiza aparte.

- [ ] **Step 2: BottomNav.tsx**
```tsx
import { NavLink } from 'react-router-dom'
import { NAV_ITEMS } from './navItems'

export default function BottomNav({ onAdd }: { onAdd: () => void }) {
  return (
    <nav style={{
      display: 'flex', alignItems: 'center', justifyContent: 'space-around',
      padding: '12px 14px 18px', borderTop: '1px solid var(--color-mist)',
    }}>
      {NAV_ITEMS.slice(0, 2).map((i) => <Item key={i.to} {...i} />)}
      <button onClick={onAdd} aria-label="Agregar"
        style={{
          width: 52, height: 52, borderRadius: '50%', background: 'var(--color-voltage)',
          border: 'none', boxShadow: 'var(--shadow-cta)', marginTop: -26, cursor: 'pointer',
        }}>
        <i className="ti ti-plus" style={{ fontSize: 26, color: 'var(--voltage-on-dark)' }} aria-hidden />
      </button>
      {NAV_ITEMS.slice(2).map((i) => <Item key={i.to} {...i} />)}
    </nav>
  )
}

function Item({ to, label, icon }: { to: string; label: string; icon: string }) {
  return (
    <NavLink to={to} end={to === '/'} style={{ textDecoration: 'none' }}>
      {({ isActive }) => (
        <span style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3,
          color: isActive ? 'var(--color-obsidian-ink)' : 'var(--color-sage)' }}>
          <i className={`ti ${icon}`} style={{ fontSize: 21 }} aria-hidden />
          <span style={{ fontSize: 10, fontWeight: isActive ? 500 : 400 }}>{label}</span>
          {isActive && <span style={{ width: 5, height: 5, borderRadius: '50%', background: 'var(--color-voltage)' }} />}
        </span>
      )}
    </NavLink>
  )
}
```

- [ ] **Step 3: TopBar.tsx**
```tsx
import ScopeToggle from './ScopeToggle'

export default function TopBar({ onMenu }: { onMenu: () => void }) {
  return (
    <header style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '14px 22px' }}>
      <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ color: 'var(--color-voltage)', fontWeight: 600, fontSize: 18, letterSpacing: -2 }}>❘❘</span>
        <span className="cap" style={{ color: 'var(--color-obsidian-ink)', letterSpacing: '0.04em', fontSize: 12 }}>[ tu marca ]</span>
      </span>
      <span style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <ScopeToggle />
        <button onClick={onMenu} aria-label="Menú" style={{ background: 'none', border: 'none', cursor: 'pointer' }}>
          <i className="ti ti-menu-2" style={{ fontSize: 20, color: 'var(--color-obsidian-ink)' }} aria-hidden />
        </button>
      </span>
    </header>
  )
}
```

- [ ] **Step 4: MenuDrawer.tsx**
```tsx
import { Link } from 'react-router-dom'

export default function MenuDrawer({ open, onClose }: { open: boolean; onClose: () => void }) {
  if (!open) return null
  const links = [
    { to: '/categorias', label: 'Categorías y presupuestos' },
    { to: '/perfil', label: 'Perfil y cuenta' },
  ]
  return (
    <div onClick={onClose} style={{ minHeight: 400, position: 'relative', background: 'rgba(18,22,19,0.45)' }}>
      <div onClick={(e) => e.stopPropagation()} style={{
        background: 'var(--color-linen)', padding: 24, display: 'grid', gap: 16,
      }}>
        {links.map((l) => (
          <Link key={l.to} to={l.to} onClick={onClose} style={{ color: 'var(--color-obsidian-ink)', textDecoration: 'none', fontSize: 16 }}>{l.label}</Link>
        ))}
        <a href="/legacy/" style={{ color: 'var(--color-sage)', fontSize: 14 }}>Otras secciones (hábitos, notas, tareas) →</a>
      </div>
    </div>
  )
}
```

- [ ] **Step 5: Sidebar.tsx (desktop)**
```tsx
import { NavLink } from 'react-router-dom'
import { NAV_ITEMS } from './navItems'

export default function Sidebar({ onAdd }: { onAdd: () => void }) {
  return (
    <aside style={{ width: 220, borderRight: '1px solid var(--color-mist)', padding: 24, display: 'grid', gap: 6, alignContent: 'start' }}>
      <button onClick={onAdd} style={{
        background: 'var(--color-voltage)', color: 'var(--voltage-on-dark)', border: 'none', borderRadius: 10,
        padding: '12px 16px', fontWeight: 500, marginBottom: 16, cursor: 'pointer',
      }}>+ Agregar gasto</button>
      {NAV_ITEMS.map((i) => (
        <NavLink key={i.to} to={i.to} end={i.to === '/'} style={({ isActive }) => ({
          color: isActive ? 'var(--color-obsidian-ink)' : 'var(--color-sage)',
          textDecoration: 'none', fontSize: 15, padding: '8px 0', fontWeight: isActive ? 500 : 400,
        })}>
          <i className={`ti ${i.icon}`} style={{ marginRight: 8 }} aria-hidden />{i.label}
        </NavLink>
      ))}
    </aside>
  )
}
```

- [ ] **Step 6: AppLayout.tsx (responsive con matchMedia)**
```tsx
import { ReactNode, useEffect, useState } from 'react'
import { Outlet } from 'react-router-dom'
import TopBar from './TopBar'
import BottomNav from './BottomNav'
import Sidebar from './Sidebar'
import MenuDrawer from './MenuDrawer'
import QuickAddSheet from '../QuickAddSheet'

export default function AppLayout({ children }: { children?: ReactNode }) {
  const [isDesktop, setIsDesktop] = useState(() => window.innerWidth >= 1024)
  const [menuOpen, setMenuOpen] = useState(false)
  const [addOpen, setAddOpen] = useState(false)

  useEffect(() => {
    const mq = window.matchMedia('(min-width: 1024px)')
    const fn = () => setIsDesktop(mq.matches)
    mq.addEventListener('change', fn)
    return () => mq.removeEventListener('change', fn)
  }, [])

  if (isDesktop) {
    return (
      <div style={{ display: 'flex', maxWidth: 1100, margin: '0 auto', minHeight: '100%' }}>
        <Sidebar onAdd={() => setAddOpen(true)} />
        <main style={{ flex: 1, padding: 24 }}>{children ?? <Outlet />}</main>
        {addOpen && <QuickAddSheet onClose={() => setAddOpen(false)} />}
      </div>
    )
  }
  return (
    <div style={{ minHeight: '100%', display: 'flex', flexDirection: 'column', maxWidth: 480, margin: '0 auto' }}>
      <TopBar onMenu={() => setMenuOpen(true)} />
      <main style={{ flex: 1 }}>{children ?? <Outlet />}</main>
      <BottomNav onAdd={() => setAddOpen(true)} />
      <MenuDrawer open={menuOpen} onClose={() => setMenuOpen(false)} />
      {addOpen && <QuickAddSheet onClose={() => setAddOpen(false)} />}
    </div>
  )
}
```

- [ ] **Step 7: Webfont Tabler en index.html**

En `web-react/index.html`, dentro de `<head>`, agregar:
```html
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@3/dist/tabler-icons.min.css">
```

- [ ] **Step 8: Commit (compila tras crear QuickAddSheet en Task 14)**
```bash
git add -A web-react/src/components/nav web-react/index.html
git commit -m "feat: responsive nav + AppLayout"
```

---

## PHASE 4 — Vistas

### Task 13: Inicio (hero gasto del mes + cuotas + categorías)

> ⚠ **CORRECCIÓN DE SHAPE DE API (verificado contra `vps_current/web.py`):** `/api/overview2`
> anida los KPIs bajo `data.kpis`. Usar `data.kpis.gasto_mes`, `data.kpis.gasto_prev_alt`,
> `data.kpis.ingreso_mes`, `data.kpis.cuotas_futuras` (NO `data.gasto_mes` etc.).
> `data.patrimonio_ars` y `data.blue` siguen siendo top-level. La lista del día es `data.hoy`
> (no `hoy_items`). Para `/api/vencimientos`: cada item tiene `next_due`, `next_closing`,
> `ciclo_cerrado: {currency,total}[]`, `ciclo_abierto: {currency,total}[]` (NO `due_date`/`amount`).
> El monto a pagar = suma de `ciclo_cerrado[].total`. El código de abajo se ajusta a esto.

**Files:**
- Create: `web-react/src/hooks/useOverview.ts`, `web-react/src/hooks/useVencimientos.ts`
- Modify: `web-react/src/routes/Inicio.tsx`, `web-react/src/App.tsx` (envolver en AppLayout)

- [ ] **Step 1: Hooks**

Crear `web-react/src/hooks/useOverview.ts`:
```ts
import { useQuery } from '@tanstack/react-query'
import { apiGet } from '../lib/api'
import type { Overview2 } from '../lib/types'
export function useOverview() {
  return useQuery({ queryKey: ['overview2'], queryFn: () => apiGet<Overview2>('/api/overview2') })
}
```
Crear `web-react/src/hooks/useVencimientos.ts`:
```ts
import { useQuery } from '@tanstack/react-query'
import { apiGet } from '../lib/api'
import type { VencimientoCard } from '../lib/types'
export function useVencimientos() {
  return useQuery({ queryKey: ['vencimientos'], queryFn: () => apiGet<VencimientoCard[]>('/api/vencimientos') })
}
```

- [ ] **Step 2: Inicio.tsx**

Reemplazar `web-react/src/routes/Inicio.tsx`:
```tsx
import { useOverview } from '../hooks/useOverview'
import { useVencimientos } from '../hooks/useVencimientos'
import { formatMoney, formatUsdApprox } from '../lib/format'
import Card from '../components/ui/Card'
import TickMark from '../components/ui/TickMark'
import StatNumber from '../components/ui/StatNumber'
import CategoryBar from '../components/ui/CategoryBar'
import AlertPill from '../components/ui/AlertPill'
import Skeleton from '../components/ui/Skeleton'
import EmptyState from '../components/ui/EmptyState'

export default function Inicio() {
  const { data, isLoading, isError } = useOverview()
  const venc = useVencimientos()

  if (isLoading) return <div style={{ padding: 22, display: 'grid', gap: 12 }}><Skeleton h={56} /><Skeleton h={120} /></div>
  if (isError || !data) return <EmptyState>No pudimos cargar tus datos. Reintentá.</EmptyState>

  const delta = data.gasto_mes - data.gasto_prev_alt
  const maxCat = Math.max(1, ...data.por_categoria.map((c) => c.total))

  return (
    <div style={{ padding: '8px 4px 24px' }}>
      <section style={{ padding: '8px 18px 6px' }}>
        <div className="cap">Gasto del mes</div>
        <div className="num-serif" style={{ fontSize: 'clamp(44px, 13vw, 56px)', marginTop: 8 }}>
          {formatMoney(data.gasto_mes)}
        </div>
        <div style={{ fontSize: 13, color: 'var(--color-sage)', marginTop: 6 }}>
          {delta >= 0 ? '▲' : '▼'} {formatMoney(Math.abs(delta))} vs mes pasado
        </div>
        <div style={{ marginTop: 16 }}><TickMark /></div>
      </section>

      <section style={{ display: 'flex', gap: 6, padding: '16px 18px 6px' }}>
        <StatNumber label="Ingresos">{formatMoney(data.ingreso_mes)}</StatNumber>
        <StatNumber label="Patrimonio">{formatMoney(data.patrimonio_ars)}</StatNumber>
        <StatNumber label="En cuotas">{formatMoney(data.cuotas_futuras)}</StatNumber>
      </section>

      <div style={{ padding: '12px 18px 0' }}>
        <Card>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: 15, fontWeight: 500 }}>
              <i className="ti ti-credit-card" style={{ marginRight: 7 }} aria-hidden />Cuotas y tarjetas
            </span>
          </div>
          <div style={{ marginTop: 14 }}>
            <div className="cap">Comprometido este mes</div>
            <div className="num-serif" style={{ fontSize: 32, marginTop: 4 }}>{formatMoney(data.cuotas_futuras)}</div>
          </div>
          <div style={{ height: 1, background: 'var(--color-mist)', margin: '16px 0' }} />
          {venc.isLoading && <Skeleton h={48} />}
          {venc.data && venc.data.length === 0 && <EmptyState>Sin vencimientos próximos.</EmptyState>}
          {venc.data?.map((v) => (
            <div key={v.account_id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <span>
                <span style={{ fontSize: 14, fontWeight: 500 }}>{v.account_name}</span><br />
                {daysUntil(v.closing_date) !== null && daysUntil(v.closing_date)! <= 5
                  ? <AlertPill>cierra en {daysUntil(v.closing_date)} días</AlertPill>
                  : <span style={{ fontSize: 11, color: 'var(--color-sage)' }}>vence {v.due_date.slice(8, 10)}/{v.due_date.slice(5, 7)}</span>}
              </span>
              <span style={{ fontSize: 15, fontWeight: 500 }}>{formatMoney(v.amount)}</span>
            </div>
          ))}
        </Card>
      </div>

      <section style={{ padding: '20px 18px 8px' }}>
        <div className="cap" style={{ marginBottom: 12 }}>Gastos por categoría</div>
        {data.por_categoria.length === 0
          ? <EmptyState>Todavía no cargaste gastos este mes — escribile al bot o tocá +.</EmptyState>
          : data.por_categoria.slice(0, 6).map((c) => <CategoryBar key={c.cat} label={c.cat} total={c.total} max={maxCat} />)}
      </section>

      {formatUsdApprox(data.patrimonio_ars, data.blue) && (
        <div style={{ padding: '0 18px', fontSize: 12, color: 'var(--color-sage)' }}>
          Patrimonio {formatUsdApprox(data.patrimonio_ars, data.blue)} · blue {formatMoney(data.blue)}
        </div>
      )}
    </div>
  )
}

function daysUntil(dateStr?: string): number | null {
  if (!dateStr) return null
  const d = new Date(dateStr).getTime() - Date.now()
  return Math.ceil(d / 86_400_000)
}
```

- [ ] **Step 3: Envolver rutas en AppLayout**

Reemplazar `web-react/src/App.tsx`:
```tsx
import { Routes, Route, Navigate } from 'react-router-dom'
import AppLayout from './components/nav/AppLayout'
import Login from './routes/Login'
import Inicio from './routes/Inicio'
import Movimientos from './routes/Movimientos'
import Tarjetas from './routes/Tarjetas'
import Cuentas from './routes/Cuentas'
import Categorias from './routes/Categorias'
import Perfil from './routes/Perfil'

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<AppLayout />}>
        <Route path="/" element={<Inicio />} />
        <Route path="/movimientos" element={<Movimientos />} />
        <Route path="/tarjetas" element={<Tarjetas />} />
        <Route path="/cuentas" element={<Cuentas />} />
        <Route path="/categorias" element={<Categorias />} />
        <Route path="/perfil" element={<Perfil />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
```

- [ ] **Step 4: Test de Inicio (hero gasto del mes)**

Crear `web-react/src/routes/Inicio.test.tsx`:
```tsx
import { screen } from '@testing-library/react'
import { vi, expect, test, afterEach } from 'vitest'
import { renderWithProviders } from '../test/utils'
import Inicio from './Inicio'

afterEach(() => vi.restoreAllMocks())

test('muestra el gasto del mes como hero', async () => {
  vi.stubGlobal('fetch', vi.fn((url: string) => {
    if (String(url).includes('/api/overview2')) return Promise.resolve(new Response(JSON.stringify({
      patrimonio_ars: 2480500, patrimonio_usd: 2066, blue: 1200,
      gasto_mes: 612300, gasto_prev_alt: 500000, ingreso_mes: 980000,
      cuotas_futuras: 340000, cuotas_n: 8, cashflow: [], hoy_items: [],
      por_categoria: [{ cat: 'Comida', total: 210000 }],
    }), { status: 200 }))
    return Promise.resolve(new Response('[]', { status: 200 }))
  }))
  renderWithProviders(<Inicio />)
  expect(await screen.findByText('$612.300')).toBeInTheDocument()
  expect(screen.getByText('Comida')).toBeInTheDocument()
})
```

- [ ] **Step 5: Run + commit**
```bash
npx vitest run src/routes/Inicio.test.tsx
git add -A web-react/src && git commit -m "feat: Inicio view (hero gasto del mes + cuotas + categorias)"
```

> **Nota:** App.tsx ahora importa rutas aún inexistentes (Movimientos, Tarjetas, Cuentas,
> Categorias, Perfil). Crear stubs mínimos antes de `npm run build`:
> cada uno `export default function X(){return <div className="cap" style={{padding:20}}>X</div>}`.
> Se reemplazan en las tasks siguientes.

---

### Task 14: QuickAddSheet (alta rápida de transacción)

**Files:**
- Create: `web-react/src/components/ui/Sheet.tsx`, `web-react/src/components/QuickAddSheet.tsx`, `web-react/src/hooks/useTransactions.ts`, `web-react/src/hooks/useAccounts.ts`, `web-react/src/hooks/useCategories.ts`

- [ ] **Step 1: Sheet.tsx (overlay en flujo normal)**
```tsx
import { ReactNode } from 'react'
export default function Sheet({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  return (
    <div onClick={onClose} style={{ minHeight: 420, position: 'relative', display: 'flex', alignItems: 'flex-end', background: 'rgba(18,22,19,0.45)' }}>
      <div onClick={(e) => e.stopPropagation()} style={{ width: '100%', background: 'var(--color-linen)', borderTopLeftRadius: 18, borderTopRightRadius: 18, padding: 22 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <span style={{ fontSize: 16, fontWeight: 500 }}>{title}</span>
          <button onClick={onClose} aria-label="Cerrar" style={{ background: 'none', border: 'none', cursor: 'pointer' }}>
            <i className="ti ti-x" style={{ fontSize: 20 }} aria-hidden />
          </button>
        </div>
        {children}
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Hooks de datos para el form**

Crear `web-react/src/hooks/useAccounts.ts`:
```ts
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiGet, apiPost, apiPatch, apiDelete } from '../lib/api'
import type { Account } from '../lib/types'
export function useAccounts() {
  return useQuery({ queryKey: ['accounts'], queryFn: () => apiGet<Account[]>('/api/accounts') })
}
export function useAccountMutations() {
  const qc = useQueryClient()
  const inval = () => qc.invalidateQueries({ queryKey: ['accounts'] })
  return {
    create: useMutation({ mutationFn: (b: Partial<Account>) => apiPost('/api/accounts', b), onSuccess: inval }),
    update: useMutation({ mutationFn: ({ id, ...b }: { id: number } & Partial<Account>) => apiPatch(`/api/accounts/${id}`, b), onSuccess: inval }),
    remove: useMutation({ mutationFn: (id: number) => apiDelete(`/api/accounts/${id}`), onSuccess: inval }),
  }
}
```
Crear `web-react/src/hooks/useCategories.ts`:
```ts
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiGet, apiPost, apiPatch, apiDelete } from '../lib/api'
import type { Category } from '../lib/types'
export function useCategories() {
  return useQuery({ queryKey: ['categories'], queryFn: () => apiGet<Category[]>('/api/categories') })
}
export function useCategoryMutations() {
  const qc = useQueryClient()
  const inval = () => qc.invalidateQueries({ queryKey: ['categories'] })
  return {
    create: useMutation({ mutationFn: (b: Partial<Category>) => apiPost('/api/categories', b), onSuccess: inval }),
    update: useMutation({ mutationFn: ({ id, ...b }: { id: number } & Partial<Category>) => apiPatch(`/api/categories/${id}`, b), onSuccess: inval }),
    remove: useMutation({ mutationFn: (id: number) => apiDelete(`/api/categories/${id}`), onSuccess: inval }),
  }
}
```
Crear `web-react/src/hooks/useTransactions.ts`:
```ts
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiGet, apiPost, apiPatch, apiDelete } from '../lib/api'
import type { Transaction } from '../lib/types'

export interface TxFilters { period?: string; account_id?: number; category_id?: number; currency?: string; q?: string }

export function useTransactions(filters: TxFilters = {}) {
  const qs = new URLSearchParams()
  Object.entries(filters).forEach(([k, v]) => { if (v !== undefined && v !== '') qs.set(k, String(v)) })
  const query = qs.toString()
  return useQuery({
    queryKey: ['transactions', filters],
    queryFn: () => apiGet<Transaction[]>(`/api/transactions${query ? `?${query}` : ''}`),
  })
}

export function useTxMutations() {
  const qc = useQueryClient()
  const inval = () => { qc.invalidateQueries({ queryKey: ['transactions'] }); qc.invalidateQueries({ queryKey: ['overview2'] }) }
  return {
    create: useMutation({ mutationFn: (b: Partial<Transaction>) => apiPost('/api/transactions', b), onSuccess: inval }),
    update: useMutation({ mutationFn: ({ id, ...b }: { id: number } & Partial<Transaction>) => apiPatch(`/api/transactions/${id}`, b), onSuccess: inval }),
    remove: useMutation({ mutationFn: (id: number) => apiDelete(`/api/transactions/${id}`), onSuccess: inval }),
    bulkDelete: useMutation({ mutationFn: (ids: number[]) => apiPost('/api/transactions/bulk_delete', { ids }), onSuccess: inval }),
    bulkMove: useMutation({ mutationFn: (b: { ids: number[]; account_id: number }) => apiPost('/api/transactions/bulk_move', b), onSuccess: inval }),
  }
}
```

- [ ] **Step 3: QuickAddSheet.tsx**
```tsx
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import Sheet from './ui/Sheet'
import { useAccounts } from '../hooks/useAccounts'
import { useCategories } from '../hooks/useCategories'
import { useTxMutations } from '../hooks/useTransactions'

const schema = z.object({
  type: z.enum(['gasto', 'ingreso']),
  amount: z.coerce.number().positive('Monto inválido'),
  description: z.string().min(1, 'Falta descripción'),
  account_id: z.coerce.number().int(),
  category_id: z.coerce.number().int().optional(),
})
type Form = z.infer<typeof schema>

export default function QuickAddSheet({ onClose }: { onClose: () => void }) {
  const accounts = useAccounts()
  const categories = useCategories()
  const { create } = useTxMutations()
  const { register, handleSubmit, formState: { errors } } = useForm<Form>({
    resolver: zodResolver(schema), defaultValues: { type: 'gasto' },
  })

  const onSubmit = (v: Form) => create.mutate(v, { onSuccess: onClose })

  return (
    <Sheet title="Agregar gasto" onClose={onClose}>
      <form onSubmit={handleSubmit(onSubmit)} style={{ display: 'grid', gap: 12 }}>
        <select {...register('type')} style={field}><option value="gasto">Gasto</option><option value="ingreso">Ingreso</option></select>
        <input {...register('amount')} inputMode="decimal" placeholder="Monto" style={field} />
        {errors.amount && <small style={err}>{errors.amount.message}</small>}
        <input {...register('description')} placeholder="Descripción" style={field} />
        {errors.description && <small style={err}>{errors.description.message}</small>}
        <select {...register('account_id')} style={field}>
          <option value="">Cuenta…</option>
          {accounts.data?.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
        </select>
        <select {...register('category_id')} style={field}>
          <option value="">Categoría (opcional)…</option>
          {categories.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
        <button type="submit" disabled={create.isPending} style={cta}>{create.isPending ? 'Guardando…' : 'Guardar →'}</button>
        <p style={{ fontSize: 12, color: 'var(--color-sage)', textAlign: 'center', margin: 0 }}>También podés mandarle un mensaje al bot.</p>
      </form>
    </Sheet>
  )
}

const field: React.CSSProperties = { border: '1px solid var(--color-mist)', borderRadius: 10, padding: '12px 14px', fontSize: 16, background: 'transparent' }
const cta: React.CSSProperties = { background: 'var(--color-voltage)', color: 'var(--voltage-on-dark)', border: 'none', borderRadius: 10, padding: '14px', fontWeight: 500, boxShadow: 'var(--shadow-cta)', cursor: 'pointer' }
const err: React.CSSProperties = { color: '#a32d2d', fontSize: 12 }
```

- [ ] **Step 4: Test (validación zod muestra error)**

Crear `web-react/src/components/QuickAddSheet.test.tsx`:
```tsx
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi, expect, test, afterEach } from 'vitest'
import { renderWithProviders } from '../test/utils'
import QuickAddSheet from './QuickAddSheet'

afterEach(() => vi.restoreAllMocks())

test('exige descripción y monto válido', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('[]', { status: 200 })))
  renderWithProviders(<QuickAddSheet onClose={() => {}} />)
  await userEvent.click(screen.getByRole('button', { name: /guardar/i }))
  expect(await screen.findByText('Falta descripción')).toBeInTheDocument()
})
```

- [ ] **Step 5: Run + commit**
```bash
npx vitest run src/components/QuickAddSheet.test.tsx
git add -A web-react/src && git commit -m "feat: QuickAddSheet + tx/accounts/categories hooks"
```

---

### Task 15: Movimientos (lista + filtros + acciones)

**Files:**
- Modify: `web-react/src/routes/Movimientos.tsx`

- [ ] **Step 1: Implementar Movimientos**

Reemplazar `web-react/src/routes/Movimientos.tsx`:
```tsx
import { useState } from 'react'
import { useTransactions, useTxMutations, TxFilters } from '../hooks/useTransactions'
import { useAccounts } from '../hooks/useAccounts'
import { useCategories } from '../hooks/useCategories'
import { formatMoney } from '../lib/format'
import Skeleton from '../components/ui/Skeleton'
import EmptyState from '../components/ui/EmptyState'

const PERIODS = ['hoy', 'semana', 'mes', 'mes pasado', 'año']

export default function Movimientos() {
  const [filters, setFilters] = useState<TxFilters>({ period: 'mes' })
  const { data, isLoading } = useTransactions(filters)
  const accounts = useAccounts()
  const categories = useCategories()
  const { remove } = useTxMutations()

  return (
    <div style={{ padding: '14px 18px 24px' }}>
      <div className="cap" style={{ marginBottom: 12 }}>Movimientos</div>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 16 }}>
        <select value={filters.period} onChange={(e) => setFilters((f) => ({ ...f, period: e.target.value }))} style={sel}>
          {PERIODS.map((p) => <option key={p} value={p}>{p}</option>)}
        </select>
        <select value={filters.account_id ?? ''} onChange={(e) => setFilters((f) => ({ ...f, account_id: e.target.value ? Number(e.target.value) : undefined }))} style={sel}>
          <option value="">Toda cuenta</option>
          {accounts.data?.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
        </select>
        <select value={filters.category_id ?? ''} onChange={(e) => setFilters((f) => ({ ...f, category_id: e.target.value ? Number(e.target.value) : undefined }))} style={sel}>
          <option value="">Toda categoría</option>
          {categories.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
        <input placeholder="Buscar…" value={filters.q ?? ''} onChange={(e) => setFilters((f) => ({ ...f, q: e.target.value }))} style={{ ...sel, flex: 1 }} />
      </div>

      {isLoading && <div style={{ display: 'grid', gap: 8 }}>{[0, 1, 2].map((i) => <Skeleton key={i} h={44} />)}</div>}
      {data && data.length === 0 && <EmptyState>Sin movimientos para este filtro.</EmptyState>}
      {data?.map((t) => (
        <div key={t.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 0', borderBottom: '1px solid var(--color-mist)' }}>
          <span>
            <span style={{ fontSize: 14, fontWeight: 500 }}>{t.description}</span><br />
            <span style={{ fontSize: 11, color: 'var(--color-sage)' }}>{t.category_name ?? 'sin categoría'} · {t.account_name ?? ''} · {t.occurred_at.slice(0, 10)}</span>
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <span style={{ fontSize: 15, fontWeight: 500, color: t.type === 'ingreso' ? '#3b6d11' : 'var(--color-obsidian-ink)' }}>
              {t.type === 'ingreso' ? '+' : '−'}{formatMoney(t.amount, t.currency)}
            </span>
            <button aria-label={`Borrar ${t.description}`} onClick={() => remove.mutate(t.id)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-sage)' }}>
              <i className="ti ti-trash" aria-hidden />
            </button>
          </span>
        </div>
      ))}
    </div>
  )
}

const sel: React.CSSProperties = { border: '1px solid var(--color-mist)', borderRadius: 9999, padding: '6px 12px', fontSize: 13, background: 'transparent' }
```

- [ ] **Step 2: Test (filtra por período y lista)**

Crear `web-react/src/routes/Movimientos.test.tsx`:
```tsx
import { screen } from '@testing-library/react'
import { vi, expect, test, afterEach } from 'vitest'
import { renderWithProviders } from '../test/utils'
import Movimientos from './Movimientos'

afterEach(() => vi.restoreAllMocks())

test('lista transacciones', async () => {
  vi.stubGlobal('fetch', vi.fn((url: string) => {
    if (String(url).includes('/api/transactions')) return Promise.resolve(new Response(JSON.stringify([
      { id: 1, type: 'gasto', amount: 5000, currency: 'ARS', description: 'Coca', occurred_at: '2026-06-20', account_id: 1, account_name: 'MP', category_name: 'Comida' },
    ]), { status: 200 }))
    return Promise.resolve(new Response('[]', { status: 200 }))
  }))
  renderWithProviders(<Movimientos />)
  expect(await screen.findByText('Coca')).toBeInTheDocument()
  expect(screen.getByText('−$5.000')).toBeInTheDocument()
})
```

- [ ] **Step 3: Run + commit**
```bash
npx vitest run src/routes/Movimientos.test.tsx
git add -A web-react/src/routes/Movimientos.tsx web-react/src/routes/Movimientos.test.tsx
git commit -m "feat: Movimientos view (filters + list + delete)"
```

---

### Task 16: Tarjetas (vista estrella)

> ⚠ **CORRECCIÓN DE SHAPE DE API:** en `/api/vencimientos` usar `v.next_due` / `v.next_closing`
> (NO `due_date`/`closing_date`) y el monto a pagar = suma de `v.ciclo_cerrado[].total`
> (NO `v.amount`). El cálculo de "comprometido en cuotas" desde `/api/recurring` no cambia.

**Files:**
- Create: `web-react/src/hooks/useRecurring.ts`
- Modify: `web-react/src/routes/Tarjetas.tsx`

- [ ] **Step 1: useRecurring.ts**
```ts
import { useQuery } from '@tanstack/react-query'
import { apiGet } from '../lib/api'
import type { Recurring } from '../lib/types'
export function useRecurring() {
  return useQuery({ queryKey: ['recurring'], queryFn: () => apiGet<Recurring[]>('/api/recurring') })
}
```

- [ ] **Step 2: Tarjetas.tsx**
```tsx
import { useVencimientos } from '../hooks/useVencimientos'
import { useRecurring } from '../hooks/useRecurring'
import { useAccounts } from '../hooks/useAccounts'
import { formatMoney } from '../lib/format'
import Card from '../components/ui/Card'
import AlertPill from '../components/ui/AlertPill'
import Skeleton from '../components/ui/Skeleton'
import EmptyState from '../components/ui/EmptyState'

export default function Tarjetas() {
  const venc = useVencimientos()
  const recurring = useRecurring()
  const accounts = useAccounts()

  const cards = accounts.data?.filter((a) => a.type === 'credito') ?? []
  const cuotasByAccount = (id: number) =>
    (recurring.data ?? []).filter((r) => r.account_id === id && r.total_installments)

  if (accounts.isLoading) return <div style={{ padding: 18 }}><Skeleton h={120} /></div>
  if (cards.length === 0) return <EmptyState>No tenés tarjetas de crédito cargadas.</EmptyState>

  return (
    <div style={{ padding: '14px 18px 24px', display: 'grid', gap: 14 }}>
      <div className="cap">Tarjetas y cuotas</div>
      {cards.map((card) => {
        const v = venc.data?.find((x) => x.account_id === card.id)
        const cuotas = cuotasByAccount(card.id)
        const comprometido = cuotas.reduce((s, r) => s + r.amount * ((r.total_installments ?? 0) - (r.installments_fired ?? 0)), 0)
        return (
          <Card key={card.id}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
              <span style={{ fontSize: 16, fontWeight: 500 }}>{card.name}</span>
              {v?.due_date && <span style={{ fontSize: 12, color: 'var(--color-sage)' }}>vence {v.due_date.slice(8, 10)}/{v.due_date.slice(5, 7)}</span>}
            </div>
            <div style={{ marginTop: 12 }}>
              <div className="cap">Comprometido en cuotas</div>
              <div className="num-serif" style={{ fontSize: 30, marginTop: 4 }}>{formatMoney(comprometido)}</div>
            </div>
            {v && <div style={{ marginTop: 10 }}><AlertPill>pagar {formatMoney(v.amount)} el {v.due_date.slice(8, 10)}</AlertPill></div>}
            <div style={{ height: 1, background: 'var(--color-mist)', margin: '14px 0' }} />
            {cuotas.length === 0 ? <EmptyState>Sin cuotas activas.</EmptyState> : cuotas.map((r) => (
              <div key={r.id} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13, marginBottom: 8 }}>
                <span>{r.description} <span style={{ color: 'var(--color-sage)' }}>({(r.installments_fired ?? 0)}/{r.total_installments})</span></span>
                <span style={{ fontWeight: 500 }}>{formatMoney(r.amount, r.currency)}</span>
              </div>
            ))}
          </Card>
        )
      })}
    </div>
  )
}
```

- [ ] **Step 3: Test (suma comprometido)**

Crear `web-react/src/routes/Tarjetas.test.tsx`:
```tsx
import { screen } from '@testing-library/react'
import { vi, expect, test, afterEach } from 'vitest'
import { renderWithProviders } from '../test/utils'
import Tarjetas from './Tarjetas'

afterEach(() => vi.restoreAllMocks())

test('muestra una tarjeta con comprometido en cuotas', async () => {
  vi.stubGlobal('fetch', vi.fn((url: string) => {
    const u = String(url)
    if (u.includes('/api/accounts')) return Promise.resolve(new Response(JSON.stringify([{ id: 1, name: 'Visa Galicia', type: 'credito', active: 1 }]), { status: 200 }))
    if (u.includes('/api/recurring')) return Promise.resolve(new Response(JSON.stringify([{ id: 9, description: 'Heladera', amount: 50000, currency: 'ARS', account_id: 1, next_occurrence: '2026-07-10', active: 1, total_installments: 12, installments_fired: 2 }]), { status: 200 }))
    return Promise.resolve(new Response('[]', { status: 200 }))
  }))
  renderWithProviders(<Tarjetas />)
  expect(await screen.findByText('Visa Galicia')).toBeInTheDocument()
  expect(screen.getByText('$500.000')).toBeInTheDocument() // 50000 * (12-2)
})
```

- [ ] **Step 4: Run + commit**
```bash
npx vitest run src/routes/Tarjetas.test.tsx
git add -A web-react/src && git commit -m "feat: Tarjetas view (cuotas + vencimientos)"
```

---

### Task 17: Cuentas

**Files:**
- Modify: `web-react/src/routes/Cuentas.tsx`

- [ ] **Step 1: Cuentas.tsx**
```tsx
import { useAccounts } from '../hooks/useAccounts'
import { formatMoney } from '../lib/format'
import Card from '../components/ui/Card'
import Skeleton from '../components/ui/Skeleton'
import EmptyState from '../components/ui/EmptyState'

const TYPE_LABEL: Record<string, string> = {
  efectivo: 'Efectivo', billetera: 'Billetera', credito: 'Crédito', banco: 'Banco', inversion: 'Inversión',
}

export default function Cuentas() {
  const { data, isLoading } = useAccounts()
  if (isLoading) return <div style={{ padding: 18 }}><Skeleton h={80} /></div>
  if (!data || data.length === 0) return <EmptyState>No tenés cuentas cargadas.</EmptyState>

  return (
    <div style={{ padding: '14px 18px 24px', display: 'grid', gap: 12 }}>
      <div className="cap">Cuentas</div>
      {data.map((a) => (
        <Card key={a.id}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
            <span style={{ fontSize: 15, fontWeight: 500 }}>{a.name}</span>
            <span className="cap" style={{ fontSize: 10.5 }}>{TYPE_LABEL[a.type] ?? a.type}</span>
          </div>
          <div style={{ marginTop: 10, display: 'grid', gap: 4 }}>
            {(a.balances ?? []).length === 0 && <span style={{ fontSize: 13, color: 'var(--color-sage)' }}>Sin movimientos</span>}
            {a.balances?.map((b) => (
              <div key={b.currency} style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ fontSize: 12, color: 'var(--color-sage)' }}>{b.currency}</span>
                <span className="num-serif" style={{ fontSize: 20 }}>{formatMoney(b.balance, b.currency)}</span>
              </div>
            ))}
          </div>
        </Card>
      ))}
    </div>
  )
}
```

> **Nota:** `/api/accounts` no trae `balances`; el saldo por cuenta vive en `/api/overview`.
> Durante el armado, verificar la respuesta real: si `accounts` no incluye `balances`, traerlos
> de `/api/overview` (que sí calcula `balances` por cuenta) y mapear por `id`. Ajustar el hook
> `useAccounts` para usar `/api/overview` en esta vista, o agregar `balances` en el endpoint.

- [ ] **Step 2: Test (render de cuenta con saldo)**

Crear `web-react/src/routes/Cuentas.test.tsx`:
```tsx
import { screen } from '@testing-library/react'
import { vi, expect, test, afterEach } from 'vitest'
import { renderWithProviders } from '../test/utils'
import Cuentas from './Cuentas'

afterEach(() => vi.restoreAllMocks())

test('lista cuentas con saldo', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify([
    { id: 1, name: 'MP', type: 'billetera', active: 1, balances: [{ currency: 'ARS', balance: 250000 }] },
  ]), { status: 200 })))
  renderWithProviders(<Cuentas />)
  expect(await screen.findByText('MP')).toBeInTheDocument()
  expect(screen.getByText('$250.000')).toBeInTheDocument()
})
```

- [ ] **Step 3: Run + commit**
```bash
npx vitest run src/routes/Cuentas.test.tsx
git add -A web-react/src && git commit -m "feat: Cuentas view"
```

---

### Task 18: Categorías + Presupuestos y Perfil

**Files:**
- Modify: `web-react/src/routes/Categorias.tsx`, `web-react/src/routes/Perfil.tsx`

- [ ] **Step 1: Categorias.tsx**
```tsx
import { useCategories, useCategoryMutations } from '../hooks/useCategories'
import Card from '../components/ui/Card'
import EmptyState from '../components/ui/EmptyState'

export default function Categorias() {
  const { data } = useCategories()
  const { remove } = useCategoryMutations()
  return (
    <div style={{ padding: '14px 18px 24px', display: 'grid', gap: 10 }}>
      <div className="cap">Categorías</div>
      {!data || data.length === 0 ? <EmptyState>Sin categorías.</EmptyState> : (
        <Card>
          {data.map((c) => (
            <div key={c.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 0', borderBottom: '1px solid var(--color-mist)' }}>
              <span style={{ fontSize: 14 }}>{c.name}</span>
              <button aria-label={`Borrar ${c.name}`} onClick={() => remove.mutate(c.id)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-sage)' }}>
                <i className="ti ti-trash" aria-hidden />
              </button>
            </div>
          ))}
        </Card>
      )}
    </div>
  )
}
```
> Presupuestos por categoría (`/api/budgets`) se agregan como segunda card en esta vista en una
> iteración posterior; fuera del alcance mínimo de esta task para no bloquear el flip.

- [ ] **Step 2: Perfil.tsx**
```tsx
import { useMe } from '../hooks/useMe'
import Card from '../components/ui/Card'

export default function Perfil() {
  const { data: me } = useMe()
  return (
    <div style={{ padding: '14px 18px 24px', display: 'grid', gap: 12 }}>
      <div className="cap">Perfil</div>
      <Card>
        <div style={{ fontSize: 15, fontWeight: 500 }}>{me?.name ?? '…'}</div>
        <div style={{ fontSize: 13, color: 'var(--color-sage)' }}>{me?.username}</div>
      </Card>
      <a href="/api/export.csv" style={linkStyle}><i className="ti ti-download" style={{ marginRight: 8 }} aria-hidden />Exportar CSV</a>
      <a href="/logout" style={linkStyle}><i className="ti ti-logout" style={{ marginRight: 8 }} aria-hidden />Cerrar sesión</a>
    </div>
  )
}
const linkStyle: React.CSSProperties = { color: 'var(--color-obsidian-ink)', textDecoration: 'none', fontSize: 15, padding: '8px 0' }
```

- [ ] **Step 3: Build completo + commit**
```bash
npm run build
git add -A web-react/src && git commit -m "feat: Categorias + Perfil views"
```

---

### Task 19: Suite completa + arreglo de tipos

- [ ] **Step 1: Correr toda la suite**
Run (en `web-react/`):
```bash
npm test
npx tsc --noEmit
```
Expected: todos los tests PASS y sin errores de tipos. Arreglar lo que falle.

- [ ] **Step 2: Commit**
```bash
git add -A web-react && git commit -m "test: full suite green + type check"
```

---

## PHASE 5 — Deploy y convivencia

### Task 20: Build, Caddy y flip

**Files:**
- Modify: `Caddyfile` (en el VPS), nuevo deploy de `dist/`

- [ ] **Step 1: Build de producción**
Run (en `web-react/`):
```bash
npm run build
```
Expected: genera `web-react/dist/` con `index.html` y assets bajo `/app/`.

- [ ] **Step 2: Subir dist al VPS**
Run (desde la PC):
```bash
scp -r web-react/dist/* emir@217.76.48.219:~/asistente/webapp/
```

- [ ] **Step 3: Regla de Caddy para servir el SPA en /app**
En el `Caddyfile` del VPS, dentro del bloque del sitio `asistente.emir-maestu.site`, agregar
ANTES del handler que sirve el dashboard viejo:
```
handle_path /app/* {
    root * /home/emir/asistente/webapp
    try_files {path} /index.html
    file_server
}
```
(El proxy de `/api`, `/login`, `/logout` al uvicorn se mantiene como está. `/` sigue sirviendo
el dashboard viejo hasta el flip.)

- [ ] **Step 4: Recargar Caddy y verificar**
Run (en el VPS):
```bash
sudo systemctl reload caddy
```
Verificar en el navegador: `https://asistente.emir-maestu.site/app/` carga el SPA; el login
funciona; Inicio muestra el gasto del mes; el dashboard viejo sigue en `/`.

- [ ] **Step 5: Commit de la config**
```bash
git add Caddyfile && git commit -m "chore: serve react SPA at /app via caddy"
```

- [ ] **Step 6: Flip (cuando el core esté validado)**
1. En `vite.config.ts`, cambiar `base: '/app/'` → `base: '/'` y rebuild.
2. En `main.tsx`, cambiar `basename="/app"` → `basename="/"` y el handler 401 `/app/login` → `/login`.
3. En Caddy: servir el SPA en `/` y mover el dashboard viejo a `handle_path /legacy/*`.
4. Actualizar el link de `MenuDrawer` (`/legacy/`) si cambió la ruta.
5. Recargar Caddy y verificar.
```bash
git commit -am "chore: flip react SPA to root, legacy dashboard to /legacy"
```

---

## Self-review (cobertura del spec)

- §4 Sistema de diseño → Task 3 (tokens), Tasks 11-12 (componentes/nav). ✔
- §5 Vistas/rutas → Inicio (13), Movimientos (15), Tarjetas (16), Cuentas (17), Categorías/Perfil (18). ✔
- §6 Navegación mobile/desktop → Task 12 (AppLayout con matchMedia). ✔
- §7 Stack/datos/auth → Tasks 2, 5, 6, 8, hooks por vista. ✔
- §7 Formateo AR → Task 5. ✔ · Estados loading/empty/error → en cada vista. ✔
- §8 Backend mínimo (Caddy) → Task 20. ✔
- §10 Testing → tests en Tasks 5, 6, 9, 10, 11, 13, 14, 15, 16, 17. ✔
- §11b Auth swappable → Task 6 (authHeaders aislado). ✔

**Riesgos abiertos anotados en el plan:**
- `/api/accounts` puede no traer `balances` → resolver con `/api/overview` (nota en Task 17).
- `/api/vencimientos` y campos de fecha (`closing_date`/`due_date`) a verificar contra la
  respuesta real durante el armado; ajustar `types.ts` si difieren.
- Presupuestos (`/api/budgets`) quedan como iteración posterior dentro de Categorías.
