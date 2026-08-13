import { type CSSProperties, type ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import Sheet from '../ui/Sheet'
import { useMe } from '../../hooks/useMe'
import { useListas } from '../../hooks/useListas'
import { useTareas } from '../../hooks/useTareas'
import { useVencimientos } from '../../hooks/useVencimientos'
import { useHabitos } from '../../hooks/useHabitos'
import { useNotas } from '../../hooks/useNotas'
import { useOverview } from '../../hooks/useOverview'
import { useBudgets, budgetPct } from '../../hooks/useBudgets'
import { useSavingsGoals } from '../../hooks/useSavingsGoals'
import { formatMoney, todayISODate } from '../../lib/format'

const INK = 'var(--color-voltage-ink, #1f7a2e)'
const AMBER = '#e0a800'

// Hoja "Más": reordenada por uso (4b). Arriba tu perfil + lo que más abrís, con
// un dato vivo en cada fila en vez de un conteo estático. El cuerpo (y por lo
// tanto sus consultas) se monta solo cuando la hoja está abierta.
export default function MoreSheet({ open, onClose }: { open: boolean; onClose: () => void }) {
  return (
    <Sheet open={open} onClose={onClose} title="Más">
      {open && <MoreBody onClose={onClose} />}
    </Sheet>
  )
}

function MoreBody({ onClose }: { onClose: () => void }) {
  const navigate = useNavigate()
  const go = (to: string) => { navigate(to); onClose() }

  const { data: me } = useMe()
  const { data: listas } = useListas()
  const { data: tareas } = useTareas('all')
  const { data: venc } = useVencimientos()
  const { data: habitos } = useHabitos(7)
  const { data: notas } = useNotas()
  const { data: overview } = useOverview()
  const { data: budgets } = useBudgets()
  const { data: goals } = useSavingsGoals()

  const initial = (me?.name?.[0] ?? '·').toUpperCase()
  const partner = me?.others?.[0]?.name

  // ── Datos vivos ──────────────────────────────────────────────────────────
  // Listas: la lista con más pendientes.
  const topLista = (listas ?? []).slice().sort((a, b) => b.pend - a.pend)[0]
  const listasSub = topLista && topLista.pend > 0
    ? `${topLista.name} · ${topLista.pend} sin tildar`
    : (listas && listas.length ? 'Todo tildado' : 'Ver listas')

  // Tareas: vencidas primero, si no pendientes.
  const today = todayISODate()
  const pend = (tareas ?? []).filter((t) => t.status === 'pendiente')
  const overdue = pend.filter((t) => t.due_at && t.due_at.slice(0, 10) < today)
  const tareasSub = overdue.length
    ? `${overdue.length} vencida${overdue.length === 1 ? '' : 's'}`
    : `${pend.length} pendiente${pend.length === 1 ? '' : 's'}`
  const tareasDanger = overdue.length > 0

  // Tarjetas: la que cierra antes.
  const nextClose = (venc ?? [])
    .filter((v) => v.next_closing)
    .sort((a, b) => (a.next_closing! < b.next_closing! ? -1 : 1))[0]
  const tarjetasSub = nextClose
    ? `${nextClose.account_name} cierra el ${Number(nextClose.next_closing!.slice(8, 10))}`
    : 'Ver tarjetas'

  // Hábitos: hechos hoy / total distintos.
  const totalHabitos = habitos?.resumen.length ?? 0
  const doneHoy = new Set(
    (habitos?.items ?? []).filter((i) => i.logged_at.slice(0, 10) === today).map((i) => i.name),
  ).size
  const habitosSub = totalHabitos ? `${doneHoy} de ${totalHabitos} hoy` : 'Ver hábitos'

  // Notas: la más reciente.
  const lastNota = notas?.[0]
  const notasSub = lastNota
    ? truncate(lastNota.text, 26)
    : 'Ver notas'

  // Cuentas: patrimonio.
  const cuentasSub = overview ? formatMoney(overview.patrimonio_ars) : 'Ver saldos'

  // Presupuestos: rojos / amarillos.
  const red = (budgets ?? []).filter((b) => budgetPct(b) >= 100).length
  const amber = (budgets ?? []).filter((b) => { const p = budgetPct(b); return p >= 80 && p < 100 }).length
  const budgetSub = red
    ? `${red} pasado${red === 1 ? '' : 's'}`
    : amber
      ? `${amber} en amarillo`
      : (budgets && budgets.length ? 'Todo en verde' : 'Sin presupuestos')
  const budgetColor = red ? 'var(--color-error)' : amber ? AMBER : 'var(--color-sage)'

  // Metas: la primera activa.
  const goal = (goals ?? []).find((g) => g.active)
  const goalPct = goal && goal.target_amount > 0
    ? Math.round((goal.current_amount / goal.target_amount) * 100)
    : 0
  const metasSub = goal ? `${goal.name} ${goalPct}%` : 'Ver metas'

  return (
    <>
      {/* Perfil */}
      <button onClick={() => go('/yo')} style={header}>
        <span style={avatar}>{initial}</span>
        <span style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', flex: 1, minWidth: 0 }}>
          <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--color-obsidian-ink)' }}>{me?.name ?? 'Mi cuenta'}</span>
          <span style={{ fontSize: 12, color: INK }}>Ver perfil y ajustes →</span>
        </span>
        {partner && <span style={partnerChip}>Con {partner}</span>}
      </button>

      {/* Lo que más usás */}
      <SectionLabel>Lo que más usás</SectionLabel>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 9 }}>
        <Tile label="Listas" sub={listasSub} onClick={() => go('/listas')} />
        <Tile label="Movimientos" sub="Buscar y filtrar" onClick={() => go('/movimientos')} />
        <Tile label="Tareas" sub={tareasSub} danger={tareasDanger} onClick={() => go('/tareas')} />
        <Tile label="Tarjetas" sub={tarjetasSub} onClick={() => go('/tarjetas')} />
      </div>

      {/* Día a día */}
      <SectionLabel>Día a día</SectionLabel>
      <Group>
        <GroupRow label="Hábitos" value={habitosSub} onClick={() => go('/habitos')} />
        <GroupRow label="Notas" value={notasSub} onClick={() => go('/notas')} last />
      </Group>

      {/* Finanzas */}
      <SectionLabel>Finanzas</SectionLabel>
      <Group>
        <GroupRow label="Cuentas" value={cuentasSub} onClick={() => go('/cuentas')} />
        <GroupRow label="Presupuestos" value={budgetSub} valueColor={budgetColor} onClick={() => go('/presupuestos')} />
        <GroupRow label="Metas" value={metasSub} onClick={() => go('/metas')} />
        <div style={{ background: 'var(--color-linen)', padding: '11px 13px', display: 'flex', flexWrap: 'wrap', gap: '2px 4px' }}>
          <MiniLink label="Tendencias" onClick={() => go('/tendencias')} />
          <span style={sep}>·</span>
          <MiniLink label="Resúmenes" onClick={() => go('/resumenes')} />
          <span style={sep}>·</span>
          <MiniLink label="Recurrentes" onClick={() => go('/recurrentes')} />
          <span style={sep}>·</span>
          <MiniLink label="Categorías" onClick={() => go('/categorias')} />
        </div>
      </Group>
    </>
  )
}

function truncate(s: string, n: number): string {
  const t = s.replace(/\s+/g, ' ').trim()
  return t.length > n ? t.slice(0, n) + '…' : t
}

// ── piezas ─────────────────────────────────────────────────────────────────

function SectionLabel({ children }: { children: ReactNode }) {
  return <div className="cap" style={{ fontSize: 10, letterSpacing: '0.1em', margin: '18px 2px 9px' }}>{children}</div>
}

function Tile({ label, sub, danger, onClick }: { label: string; sub: string; danger?: boolean; onClick: () => void }) {
  return (
    <button onClick={onClick} style={tile}>
      <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--color-obsidian-ink)' }}>{label}</div>
      <div style={{ fontSize: 10.5, color: danger ? 'var(--color-error)' : 'var(--color-sage)', marginTop: 2 }}>{sub}</div>
    </button>
  )
}

function Group({ children }: { children: ReactNode }) {
  return (
    <div style={{ border: '1px solid var(--color-mist)', borderRadius: 13, overflow: 'hidden' }}>
      {children}
    </div>
  )
}

function GroupRow({ label, value, valueColor, onClick, last }: {
  label: string; value: string; valueColor?: string; onClick: () => void; last?: boolean
}) {
  return (
    <button onClick={onClick} style={{ ...groupRow, borderBottom: last ? 'none' : '1px solid var(--color-mist)' }}>
      <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--color-obsidian-ink)', flex: 1, textAlign: 'left' }}>{label}</span>
      <span style={{ fontSize: 11, color: valueColor ?? 'var(--color-sage)' }}>{value}</span>
    </button>
  )
}

function MiniLink({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button onClick={onClick} style={miniLink}>{label}</button>
  )
}

const header: CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 11, width: '100%',
  background: 'none', border: 'none', cursor: 'pointer', font: 'inherit', textAlign: 'left',
  padding: '2px 2px 14px', marginBottom: 4, borderBottom: '1px solid var(--color-mist)',
}
const avatar: CSSProperties = {
  width: 38, height: 38, borderRadius: '50%', flexShrink: 0,
  background: 'rgba(43,238,75,0.22)', color: INK,
  display: 'inline-flex', alignItems: 'center', justifyContent: 'center', fontSize: 15, fontWeight: 600,
}
const partnerChip: CSSProperties = {
  flexShrink: 0, fontSize: 11, fontWeight: 600, color: 'var(--color-sage)',
  border: '1px solid var(--color-mist)', borderRadius: 9999, padding: '6px 11px',
}
const tile: CSSProperties = {
  display: 'block', textAlign: 'left', width: '100%',
  padding: '12px 13px', borderRadius: 13, border: '1px solid var(--color-mist)',
  background: 'var(--color-linen)', cursor: 'pointer', font: 'inherit',
}
const groupRow: CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 10, width: '100%',
  padding: '12px 13px', background: 'var(--color-linen)', border: 'none',
  cursor: 'pointer', font: 'inherit',
}
const miniLink: CSSProperties = {
  background: 'none', border: 'none', cursor: 'pointer', font: 'inherit',
  fontSize: 12.5, fontWeight: 500, color: 'var(--color-obsidian-ink)', padding: 0,
}
const sep: CSSProperties = { fontSize: 12.5, color: 'var(--color-sage)' }
