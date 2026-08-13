import { type CSSProperties, type ReactNode, useState, useEffect, useDeferredValue } from 'react'
import { Link, useNavigate, useOutletContext } from 'react-router-dom'
import { useTareas } from '../hooks/useTareas'
import { useNotas } from '../hooks/useNotas'
import { useEventos } from '../hooks/useEventos'
import { useRecordatorios } from '../hooks/useRecordatorios'
import { apiGet } from '../lib/api'
import { useQuery } from '@tanstack/react-query'
import { type Transaction } from '../lib/types'
import { formatMoney } from '../lib/format'
import { type QuickType } from '../components/QuickAddSheet'
import { type LayoutCtx } from '../components/nav/AppLayout'
import EmptyState from '../components/ui/EmptyState'

// ── helpers ──────────────────────────────────────────────────────────────────

function normalize(s: string) {
  return s.toLowerCase()
}
function matches(q: string, ...fields: (string | null | undefined)[]): boolean {
  const nq = normalize(q)
  return fields.some((f) => f && normalize(f).includes(nq))
}

const INK = 'var(--color-voltage-ink, #1f7a2e)'
type Filter = 'todo' | 'plata' | 'agenda' | 'notas'
type Kind = 'plata' | 'agenda' | 'notas'

// ── acciones buscables ────────────────────────────────────────────────────────
// Los atajos también se buscan: así se descubren funciones nuevas (4a). Cada uno
// abre la hoja de "Agregar" (verbo "Hacer") o navega a una sección (verbo "Ver").

interface ActionDef {
  icon: string
  label: string
  keywords: string
  kind: Kind
  add?: QuickType
  to?: string
}

const ACTIONS: ActionDef[] = [
  { icon: 'ti-plus', label: 'Cargar gasto', keywords: 'gasto cargar comprar nafta super compra pagar plata', kind: 'plata', add: 'gasto' },
  { icon: 'ti-arrows-left-right', label: 'Ver movimientos', keywords: 'movimientos gastos ingresos historial plata', kind: 'plata', to: '/movimientos' },
  { icon: 'ti-credit-card', label: 'Ver tarjetas', keywords: 'tarjetas credito resumen cierre vencimiento', kind: 'plata', to: '/tarjetas' },
  { icon: 'ti-wallet', label: 'Ver cuentas', keywords: 'cuentas saldos plata banco efectivo', kind: 'plata', to: '/cuentas' },
  { icon: 'ti-target', label: 'Ver presupuestos', keywords: 'presupuesto tope limite gasto', kind: 'plata', to: '/presupuestos' },
  { icon: 'ti-tags', label: 'Ver categorías', keywords: 'categorias etiquetas color emoji', kind: 'plata', to: '/categorias' },
  { icon: 'ti-flag', label: 'Ver metas', keywords: 'metas ahorro objetivo', kind: 'plata', to: '/metas' },
  { icon: 'ti-calendar-plus', label: 'Nuevo evento', keywords: 'evento agenda cita reunion calendario', kind: 'agenda', add: 'evento' },
  { icon: 'ti-bell', label: 'Nuevo recordatorio', keywords: 'recordatorio recordame aviso alarma', kind: 'agenda', add: 'recordatorio' },
  { icon: 'ti-calendar', label: 'Ver agenda', keywords: 'agenda eventos recordatorios calendario', kind: 'agenda', to: '/agenda' },
  { icon: 'ti-checkbox', label: 'Nueva tarea', keywords: 'tarea pendiente hacer todo', kind: 'notas', add: 'tarea' },
  { icon: 'ti-note', label: 'Nueva nota', keywords: 'nota anotar apunte', kind: 'notas', add: 'nota' },
  { icon: 'ti-shopping-cart', label: 'Ver listas', keywords: 'listas super compras mercado', kind: 'notas', to: '/listas' },
  { icon: 'ti-flame', label: 'Ver hábitos', keywords: 'habitos racha entrenar rutina', kind: 'notas', to: '/habitos' },
]

// ── main ──────────────────────────────────────────────────────────────────────

export default function Buscar() {
  const nav = useNavigate()
  const { openAdd } = useOutletContext<LayoutCtx>()
  const [rawQ, setRawQ] = useState('')
  const [filter, setFilter] = useState<Filter>('todo')
  const q = useDeferredValue(rawQ.trim())

  // fuentes de datos
  const { data: tareas } = useTareas('all')
  const { data: notas } = useNotas()
  const { data: eventos } = useEventos(false)
  const { data: eventosPast } = useEventos(true)
  const { data: recordatorios } = useRecordatorios(true)

  // Movimientos: búsqueda server-side sobre TODO el historial (debounce 300ms).
  const [debouncedQ, setDebouncedQ] = useState('')
  useEffect(() => {
    const id = setTimeout(() => setDebouncedQ(rawQ.trim()), 300)
    return () => clearTimeout(id)
  }, [rawQ])
  const { data: txResults } = useQuery({
    queryKey: ['transactions', 'buscar', debouncedQ],
    enabled: debouncedQ.length > 0,
    queryFn: async () => {
      const res = await apiGet<{ items: Transaction[] }>(`/api/transactions?q=${encodeURIComponent(debouncedQ)}&limit=50`)
      return res.items ?? []
    },
  })

  // filtros
  const allEventos = [...(eventos ?? []), ...(eventosPast ?? [])]
  const filteredActions = q ? ACTIONS.filter((a) => matches(q, a.label, a.keywords)) : []
  const filteredTareas = q ? (tareas ?? []).filter((t) => matches(q, t.text)) : []
  const filteredNotas = q ? (notas ?? []).filter((n) => matches(q, n.text, ...n.tags)) : []
  const filteredEventos = q ? allEventos.filter((e) => matches(q, e.title, e.location, e.notes)) : []
  const filteredRecs = q ? (recordatorios ?? []).filter((r) => matches(q, r.text)) : []
  const filteredTx = debouncedQ ? (txResults ?? []) : []

  // aplicar chip
  const showKind = (k: Kind) => filter === 'todo' || filter === k
  const actions = filteredActions.filter((a) => showKind(a.kind))
  const showTx = showKind('plata')
  const showAgenda = showKind('agenda')
  const showTareasNotas = showKind('notas')

  const total = actions.length
    + (showTx ? filteredTx.length : 0)
    + (showAgenda ? filteredEventos.length + filteredRecs.length : 0)
    + (showTareasNotas ? filteredTareas.length + filteredNotas.length : 0)

  const run = (a: ActionDef) => { if (a.add) openAdd(a.add); else if (a.to) nav(a.to) }

  return (
    <div style={{ padding: '16px 18px 24px', display: 'grid', gap: 0 }}>
      {/* Caja de búsqueda */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 11 }}>
        <div style={searchBox}>
          <i className="ti ti-search" style={{ fontSize: 16, color: 'var(--color-obsidian-ink)' }} aria-hidden />
          <input
            type="search"
            placeholder="Buscar en todo…"
            value={rawQ}
            onChange={(e) => setRawQ(e.target.value)}
            autoFocus
            style={searchInput}
          />
          {rawQ && (
            <button onClick={() => setRawQ('')} aria-label="Limpiar" style={clearBtn}>
              <i className="ti ti-x" style={{ fontSize: 15, color: 'var(--color-sage)' }} aria-hidden />
            </button>
          )}
        </div>
        <button onClick={() => nav(-1)} style={doneBtn}>Listo</button>
      </div>

      {/* Chips de filtro */}
      <div style={{ display: 'flex', gap: 7, padding: '14px 0 14px', borderBottom: '1px solid var(--color-mist)' }}>
        {([['todo', 'Todo'], ['plata', 'Plata'], ['agenda', 'Agenda'], ['notas', 'Notas']] as [Filter, string][]).map(([v, label]) => (
          <button key={v} onClick={() => setFilter(v)} style={filter === v ? chipOn : chipOff}>{label}</button>
        ))}
      </div>

      {/* Sin consulta */}
      {!q && (
        <div style={{ textAlign: 'center', padding: '40px 16px', color: 'var(--color-sage)', fontSize: 14 }}>
          <i className="ti ti-search" style={{ fontSize: 28, display: 'block', marginBottom: 8, opacity: 0.5 }} aria-hidden />
          Buscá movimientos, agenda, tareas y notas. Los atajos también aparecen acá.
        </div>
      )}

      {/* Sin resultados */}
      {q && total === 0 && (
        <div style={{ marginTop: 16 }}><EmptyState>Sin resultados para "{q}"</EmptyState></div>
      )}

      {/* Acciones */}
      {actions.length > 0 && (
        <Section label="Acciones">
          {actions.map((a, i) => (
            <RowButton key={a.label} onClick={() => run(a)} last={i === actions.length - 1}>
              <i className={`ti ${a.icon}`} style={{ fontSize: 17, color: a.add ? INK : 'var(--color-sage)', flexShrink: 0 }} aria-hidden />
              <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--color-obsidian-ink)', flex: 1, textAlign: 'left' }}>{a.label}</span>
              <span style={{ fontSize: 11, fontWeight: 600, color: a.add ? INK : 'var(--color-sage)' }}>{a.add ? 'Hacer' : 'Ver'}</span>
            </RowButton>
          ))}
        </Section>
      )}

      {/* Movimientos */}
      {showTx && filteredTx.length > 0 && (
        <Section label="Movimientos" count={filteredTx.length}>
          {filteredTx.slice(0, 6).map((t, i, arr) => (
            <RowLink key={`tx-${t.id}`} to="/movimientos" last={i === arr.length - 1 && filteredTx.length <= 6}>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={rowTitle}>{t.description}</div>
                <div style={rowSub}>{t.occurred_at.slice(0, 10)}{t.acc_name || t.account_name ? ` · ${t.acc_name ?? t.account_name}` : ''}</div>
              </div>
              <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--color-obsidian-ink)', flexShrink: 0 }}>
                {t.type === 'gasto' ? '−' : '+'}{formatMoney(Math.abs(t.amount), t.currency)}
              </span>
            </RowLink>
          ))}
          {filteredTx.length > 6 && (
            <Link to="/movimientos" style={moreLink}>Ver los {filteredTx.length} en Movimientos</Link>
          )}
        </Section>
      )}

      {/* Agenda */}
      {showAgenda && (filteredEventos.length + filteredRecs.length) > 0 && (
        <Section label="Agenda" count={filteredEventos.length + filteredRecs.length}>
          {filteredEventos.map((e, i) => (
            <RowLink key={`e-${e.id}`} to="/agenda" last={i === filteredEventos.length - 1 && filteredRecs.length === 0}>
              <i className="ti ti-calendar-event" style={rowIcon} aria-hidden />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={rowTitle}>{e.title}</div>
                <div style={rowSub}>{e.starts_at.slice(0, 16).replace('T', ' ')}{e.location ? ` · ${e.location}` : ''}</div>
              </div>
            </RowLink>
          ))}
          {filteredRecs.map((r, i) => (
            <RowLink key={`r-${r.id}`} to="/agenda" last={i === filteredRecs.length - 1}>
              <i className="ti ti-bell" style={rowIcon} aria-hidden />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={rowTitle}>{r.text}</div>
                <div style={rowSub}>{r.remind_at.slice(0, 16).replace('T', ' ')}</div>
              </div>
            </RowLink>
          ))}
        </Section>
      )}

      {/* Tareas y notas */}
      {showTareasNotas && (filteredTareas.length + filteredNotas.length) > 0 && (
        <Section label="Tareas y notas" count={filteredTareas.length + filteredNotas.length}>
          {filteredTareas.map((t, i) => (
            <RowLink key={`t-${t.id}`} to="/tareas" last={i === filteredTareas.length - 1 && filteredNotas.length === 0}>
              <span style={checkbox} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={rowTitle}>{t.text}</div>
                <div style={rowSub}>{t.priority} · {t.status}</div>
              </div>
            </RowLink>
          ))}
          {filteredNotas.map((n, i) => (
            <RowLink key={`n-${n.id}`} to="/notas" last={i === filteredNotas.length - 1}>
              <i className="ti ti-note" style={rowIcon} aria-hidden />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={rowTitle}>{n.text.slice(0, 80)}{n.text.length > 80 ? '…' : ''}</div>
                {n.tags.length > 0 && <div style={rowSub}>{n.tags.join(', ')}</div>}
              </div>
              <span style={{ fontSize: 11, color: 'var(--color-sage)', flexShrink: 0 }}>nota</span>
            </RowLink>
          ))}
        </Section>
      )}
    </div>
  )
}

// ── piezas ─────────────────────────────────────────────────────────────────

function Section({ label, count, children }: { label: string; count?: number; children: ReactNode }) {
  return (
    <>
      <div className="cap" style={{ fontSize: 10, letterSpacing: '0.1em', padding: '18px 2px 8px' }}>
        {label}{count != null && <span style={{ opacity: 0.7 }}> · {count}</span>}
      </div>
      <div style={{ border: '1px solid var(--color-mist)', borderRadius: 14, overflow: 'hidden' }}>{children}</div>
    </>
  )
}

function RowButton({ onClick, last, children }: { onClick: () => void; last?: boolean; children: ReactNode }) {
  return (
    <button onClick={onClick} style={{ ...rowBase, width: '100%', border: 'none', cursor: 'pointer', font: 'inherit', borderBottom: last ? 'none' : '1px solid var(--color-mist)' }}>
      {children}
    </button>
  )
}

function RowLink({ to, last, children }: { to: string; last?: boolean; children: ReactNode }) {
  return (
    <Link to={to} style={{ ...rowBase, textDecoration: 'none', borderBottom: last ? 'none' : '1px solid var(--color-mist)' }}>
      {children}
    </Link>
  )
}

const searchBox: CSSProperties = {
  flex: 1, display: 'flex', alignItems: 'center', gap: 9,
  background: 'var(--color-linen)', border: '1.6px solid var(--color-obsidian-ink)',
  borderRadius: 12, padding: '11px 13px',
}
const searchInput: CSSProperties = {
  flex: 1, minWidth: 0, border: 'none', outline: 'none', background: 'transparent',
  fontSize: 14, color: 'var(--color-obsidian-ink)', font: 'inherit',
}
const clearBtn: CSSProperties = { background: 'none', border: 'none', cursor: 'pointer', padding: 0, display: 'inline-flex' }
const doneBtn: CSSProperties = {
  background: 'none', border: 'none', cursor: 'pointer', font: 'inherit',
  fontSize: 13, fontWeight: 500, color: 'var(--color-sage)', flexShrink: 0,
}
const chipOn: CSSProperties = {
  fontSize: 11.5, fontWeight: 600, color: 'var(--voltage-on-dark)', background: 'var(--color-voltage)',
  border: 'none', borderRadius: 9999, padding: '7px 13px', cursor: 'pointer', font: 'inherit',
}
const chipOff: CSSProperties = {
  fontSize: 11.5, fontWeight: 600, color: 'var(--color-obsidian-ink)', background: 'transparent',
  border: '1px solid var(--color-mist)', borderRadius: 9999, padding: '7px 13px', cursor: 'pointer', font: 'inherit',
}
const rowBase: CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 11, padding: '12px 14px',
  background: 'var(--color-linen)', color: 'var(--color-obsidian-ink)',
}
const rowTitle: CSSProperties = { fontSize: 13, fontWeight: 500, color: 'var(--color-obsidian-ink)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }
const rowSub: CSSProperties = { fontSize: 10.5, color: 'var(--color-sage)', marginTop: 1 }
const rowIcon: CSSProperties = { fontSize: 16, color: 'var(--color-sage)', flexShrink: 0 }
const checkbox: CSSProperties = { width: 17, height: 17, border: '1.6px solid var(--color-mist)', borderRadius: 5, flexShrink: 0 }
const moreLink: CSSProperties = {
  display: 'block', textAlign: 'center', padding: '11px 14px', fontSize: 11.5, fontWeight: 600,
  color: INK, textDecoration: 'none', background: 'var(--color-linen)',
}
