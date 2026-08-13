import { useState, type CSSProperties } from 'react'
import { Link, useNavigate, useOutletContext } from 'react-router-dom'
import ShortcutsEditor from '../components/ShortcutsEditor'
import { getShortcutIds, setShortcutIds, shortcutById } from '../lib/shortcuts'
import { useOverview } from '../hooks/useOverview'
import { useVencimientos } from '../hooks/useVencimientos'
import { useRecurring } from '../hooks/useRecurring'
import { useMe } from '../hooks/useMe'
import { cicloEnCursoTotal } from '../lib/cards'
import { formatMoney } from '../lib/format'
import { Money, usePrivacy } from '../lib/privacy'
import { type HoyItem } from '../lib/types'
import { type LayoutCtx } from '../components/nav/AppLayout'
import Card from '../components/ui/Card'
import EmptyState from '../components/ui/EmptyState'
import InstallNotifyBanner from '../components/InstallNotifyBanner'

function todayLabel(): string {
  return new Intl.DateTimeFormat('es-AR', { weekday: 'long', day: 'numeric', month: 'long' }).format(new Date())
}

const TIPO_ICON: Record<string, string> = {
  evento: 'ti-calendar-event', recordatorio: 'ti-bell', tarea: 'ti-checkbox', recurrente: 'ti-repeat',
}
const TIPO_ROUTE: Record<string, string> = {
  evento: '/agenda', recordatorio: '/agenda', tarea: '/tareas', recurrente: '/recurrentes',
}

function HoySkeleton() {
  const Skel = ({ h, w = '100%' }: { h: number; w?: string | number }) =>
    <span aria-hidden className="nf-skel" style={{ height: h, width: w, display: 'block', borderRadius: 12 }} />
  return (
    <div style={{ padding: '8px 18px 24px', display: 'grid', gap: 14 }}>
      <Skel h={20} w="45%" /><Skel h={190} /><Skel h={120} /><Skel h={140} />
    </div>
  )
}

export default function Hoy() {
  const { openAdd } = useOutletContext<LayoutCtx>()
  const nav = useNavigate()
  const { hidden, toggle } = usePrivacy()
  const overview = useOverview()
  const venc = useVencimientos()
  const recurring = useRecurring()
  const { data: me } = useMe()
  const [shortcutIds, setIds] = useState(getShortcutIds())
  const [editOpen, setEditOpen] = useState(false)

  if (overview.isLoading) return <HoySkeleton />
  if (overview.isError || !overview.data) return <EmptyState>No pudimos cargar tus datos. Reintentá.</EmptyState>

  const k = overview.data.kpis
  const hoy: HoyItem[] = overview.data.hoy
  const aPagar = cicloEnCursoTotal(venc.data, recurring.data)
  const partner = me?.others?.[0]?.name

  return (
    <div style={{ padding: '8px 18px 24px', display: 'grid', gap: 0 }}>
      {/* Título + fecha */}
      <div className="num-serif" style={{ fontSize: 'clamp(28px, 8vw, 34px)' }}>Inicio</div>
      <div style={{ fontSize: 13, color: 'var(--color-sage)', marginTop: 3, textTransform: 'capitalize' }}>{todayLabel()}</div>

      {/* Tarjeta de plata + acciones rápidas */}
      <Card style={{ marginTop: 16, padding: '15px 15px 13px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <span className="cap" style={{ fontSize: 10 }}>Disponible</span>
          <Link to="/finanzas" style={{ fontSize: 11, fontWeight: 500, color: 'var(--color-sage)', textDecoration: 'none' }}>Ver finanzas →</Link>
        </div>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginTop: 2 }}>
          <span className="num-serif" style={{ fontSize: 'clamp(26px, 8vw, 31px)' }}><Money value={k.disponible} /></span>
          <button onClick={toggle} aria-label={hidden ? 'Mostrar montos' : 'Ocultar montos'}
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-sage)', padding: 0, display: 'inline-flex' }}>
            <i className={`ti ${hidden ? 'ti-eye-off' : 'ti-eye'}`} style={{ fontSize: 16 }} aria-hidden />
          </button>
        </div>
        <div style={{ fontSize: 11.5, color: 'var(--color-sage)', marginTop: 5 }}>
          Gastado {formatMoney(k.gasto_mes)} · A pagar {formatMoney(aPagar)} este mes
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8, marginTop: 14 }}>
          <QuickTile icon="ti-plus" label="Cargar gasto" onClick={() => openAdd('gasto')} />
          <QuickTile icon="ti-arrows-left-right" label="Movimientos" onClick={() => nav('/movimientos')} />
          <QuickTile icon="ti-credit-card" label="Tarjetas" onClick={() => nav('/tarjetas')} />
        </div>
      </Card>

      {/* Tus atajos (personalizables) */}
      <div style={{ padding: '20px 0 8px', display: 'flex', alignItems: 'baseline', justifyContent: 'space-between' }}>
        <span className="cap" style={{ fontSize: 10 }}>Tus atajos</span>
        <button onClick={() => setEditOpen(true)} style={{ background: 'none', border: 'none', cursor: 'pointer', font: 'inherit', fontSize: 11, fontWeight: 600, color: 'var(--color-voltage-ink, #1f7a2e)' }}>Editar</button>
      </div>
      <div style={{ display: 'flex', gap: 9, overflowX: 'auto', margin: '0 -18px', padding: '0 18px 2px' }}>
        {shortcutIds.map((id) => {
          const s = shortcutById(id)
          if (!s) return null
          const act = s.action
          const onClick = act.type === 'route' ? () => nav(act.to) : () => openAdd(act.addType)
          return <Shortcut key={id} icon={s.icon} title={s.label} sub={s.sub} badge={s.shareable ? partner : undefined} onClick={onClick} />
        })}
      </div>
      <ShortcutsEditor open={editOpen} onClose={() => setEditOpen(false)} ids={shortcutIds}
        onSave={(n) => { setShortcutIds(n); setIds(n) }} />

      {/* Tu día */}
      <div style={{ padding: '22px 0 8px' }}><span className="cap" style={{ fontSize: 10 }}>Tu día</span></div>
      {hoy.length === 0
        ? <EmptyState>Nada agendado para hoy ✨</EmptyState>
        : (
          <Card style={{ padding: 0, overflow: 'hidden' }}>
            {hoy.map((item, i) => (
              <Link key={i} to={TIPO_ROUTE[item.tipo] ?? '/'}
                style={{ display: 'flex', gap: 10, alignItems: 'center', padding: '13px 14px', textDecoration: 'none', color: 'inherit',
                  borderBottom: i < hoy.length - 1 ? '1px solid var(--color-mist)' : 'none' }}>
                <i className={`ti ${TIPO_ICON[item.tipo] ?? 'ti-point'}`} style={{ fontSize: 16, color: 'var(--color-sage)', flexShrink: 0 }} aria-hidden />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13.5, fontWeight: 600 }}>
                    <span style={{ color: 'var(--color-sage)', fontWeight: 500, marginRight: 6 }}>{item.hora}</span>{item.titulo}
                  </div>
                  {item.sub && <div style={{ fontSize: 11.5, color: 'var(--color-sage)', marginTop: 2 }}>{item.sub}</div>}
                </div>
                <i className="ti ti-chevron-right" style={{ fontSize: 15, color: 'var(--color-sage)', flexShrink: 0 }} aria-hidden />
              </Link>
            ))}
          </Card>
        )}

      <div style={{ marginTop: 16 }}><InstallNotifyBanner /></div>
    </div>
  )
}

// Acción rápida de finanzas (tile verde tenue).
function QuickTile({ icon, label, onClick }: { icon: string; label: string; onClick: () => void }) {
  return (
    <button onClick={onClick} style={tile}>
      <i className={`ti ${icon}`} style={{ fontSize: 21, color: 'var(--color-voltage-ink, #1f7a2e)' }} aria-hidden />
      <span style={{ fontSize: 11.5, fontWeight: 600, color: 'var(--color-voltage-ink, #1f7a2e)', textAlign: 'center' }}>{label}</span>
    </button>
  )
}

// Atajo del riel horizontal.
function Shortcut({ icon, title, sub, badge, onClick }: { icon: string; title: string; sub: string; badge?: string; onClick: () => void }) {
  return (
    <button onClick={onClick} style={shortcut}>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
        <i className={`ti ${icon}`} style={{ fontSize: 18, color: 'var(--color-obsidian-ink)' }} aria-hidden />
        {badge && <span style={sBadge}>{badge.slice(0, 1).toUpperCase()}</span>}
      </div>
      <div style={{ fontSize: 12.5, fontWeight: 600, marginTop: 20, lineHeight: 1.25, textAlign: 'left' }}>{title}</div>
      <div style={{ fontSize: 10.5, color: 'var(--color-sage)', marginTop: 2, textAlign: 'left' }}>{sub}</div>
    </button>
  )
}

const tile: CSSProperties = {
  background: 'rgba(43,238,75,0.12)', border: 'none', borderRadius: 13, padding: '12px 6px 10px',
  display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 7, cursor: 'pointer', font: 'inherit',
}
const shortcut: CSSProperties = {
  flex: 'none', width: 122, background: 'var(--color-linen)', border: '1px solid var(--color-mist)',
  borderRadius: 14, padding: 12, cursor: 'pointer', font: 'inherit', color: 'var(--color-obsidian-ink)',
}
const sBadge: CSSProperties = {
  width: 16, height: 16, borderRadius: '50%', background: 'rgba(43,238,75,0.25)',
  fontSize: 8.5, lineHeight: '16px', fontWeight: 600, color: 'var(--color-voltage-ink, #1f7a2e)', textAlign: 'center',
}
