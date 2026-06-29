import { Link } from 'react-router-dom'
import { useOverview } from '../hooks/useOverview'
import { useTareas } from '../hooks/useTareas'
import { useVencimientos } from '../hooks/useVencimientos'
import { useEventos } from '../hooks/useEventos'
import { useRecordatorios } from '../hooks/useRecordatorios'
import { useRecurring } from '../hooks/useRecurring'
import { useHabitos } from '../hooks/useHabitos'
import { useListas } from '../hooks/useListas'
import { useNotas } from '../hooks/useNotas'
import { cicloEnCursoTotal } from '../lib/cards'
import { formatMoney, cleanReminderText } from '../lib/format'
import { type HoyItem } from '../lib/types'
import Card from '../components/ui/Card'
import EmptyState from '../components/ui/EmptyState'
import InstallNotifyBanner from '../components/InstallNotifyBanner'
import SectionCard from '../components/ui/SectionCard'

// --- Date header ---
function todayLabel(): string {
  return new Intl.DateTimeFormat('es-AR', { weekday: 'long', day: 'numeric', month: 'long' }).format(new Date())
}

// --- Upcoming item date/time label ---
function whenDate(s: string): Date { return new Date((s || '').replace(' ', 'T')) }
function whenLabel(s: string): string {
  const d = whenDate(s)
  const day = new Intl.DateTimeFormat('es-AR', { weekday: 'short', day: 'numeric', month: 'short' }).format(d)
  const time = new Intl.DateTimeFormat('es-AR', { hour: '2-digit', minute: '2-digit' }).format(d)
  return `${day} · ${time}`
}

// --- HoyItem icon map ---
const TIPO_ICON: Record<string, string> = {
  evento: 'ti-calendar-event',
  recordatorio: 'ti-bell',
  tarea: 'ti-checkbox',
  recurrente: 'ti-repeat',
}

// --- HoyItem → ruta (para hacer cada item clickeable) ---
const TIPO_ROUTE: Record<string, string> = {
  evento: '/agenda',
  recordatorio: '/agenda',
  tarea: '/tareas',
  recurrente: '/recurrentes',
}

function TipoIcon({ tipo }: { tipo: string }) {
  const icon = TIPO_ICON[tipo] ?? 'ti-point'
  return <i className={`ti ${icon}`} aria-hidden style={{ fontSize: 16, color: 'var(--color-sage)', flexShrink: 0 }} />
}

// --- Priority chip ---
const PRIORITY_COLOR: Record<string, string> = {
  alta: '#a32d2d',
  media: '#b87c20',
  baja: 'var(--color-sage)',
}

function PriorityChip({ priority }: { priority: string }) {
  return (
    <span style={{
      fontSize: 10, padding: '2px 7px', borderRadius: 6,
      color: PRIORITY_COLOR[priority] ?? 'var(--color-sage)',
      border: `1px solid ${PRIORITY_COLOR[priority] ?? 'var(--color-mist)'}`,
      fontWeight: 500,
    }}>{priority}</span>
  )
}

// --- Skeleton ---
function HoySkeleton() {
  function Skel({ h, w = '100%' }: { h: number; w?: string | number }) {
    return <span aria-hidden className="nf-skel" style={{ height: h, width: w, display: 'block' }} />
  }
  return (
    <div style={{ padding: '8px 4px 24px' }}>
      <section style={{ padding: '8px 18px 20px', display: 'grid', gap: 8 }}>
        <Skel h={12} w="25%" />
        <Skel h={20} w="55%" />
      </section>
      <div style={{ padding: '0 18px', display: 'grid', gap: 14 }}>
        <Skel h={80} w="100%" />
        <Skel h={64} w="100%" />
        <Skel h={100} w="100%" />
      </div>
    </div>
  )
}

export default function Hoy() {
  const overview = useOverview()
  const tareas = useTareas('pendiente')
  const venc = useVencimientos()
  const recurring = useRecurring()
  const eventos = useEventos(false)
  const recordatorios = useRecordatorios(false)
  const habitos = useHabitos()
  const listas = useListas()
  const notas = useNotas()

  if (overview.isLoading) return <HoySkeleton />
  if (overview.isError || !overview.data) return <EmptyState>No pudimos cargar tus datos. Reintentá.</EmptyState>

  const hoy: HoyItem[] = overview.data.hoy
  const k = overview.data.kpis

  const pendientes = (tareas.data ?? []).filter((t) => t.status === 'pendiente')
  const top3 = pendientes.slice(0, 3)

  // "Lo que viene": próximos eventos + recordatorios (después de hoy)
  const endToday = new Date(); endToday.setHours(23, 59, 59, 999)
  const upcoming = [
    ...(eventos.data ?? []).map((e) => ({ id: `e${e.id}`, kind: 'evento', when: e.starts_at, title: e.title })),
    ...(recordatorios.data ?? []).filter((r) => !r.event_id).map((r) => ({ id: `r${r.id}`, kind: 'recordatorio', when: r.remind_at, title: cleanReminderText(r.text) })),
  ]
    .filter((i) => i.when && whenDate(i.when) > endToday)
    .sort((a, b) => whenDate(a.when).getTime() - whenDate(b.when).getTime())
    .slice(0, 5)

  const nHab = habitos.data?.resumen?.length ?? 0
  const nList = listas.data?.length ?? 0
  const nNot = notas.data?.length ?? 0

  return (
    <div style={{ padding: '8px 4px 24px' }}>
      {/* Header */}
      <section style={{ padding: '8px 18px 20px' }}>
        <div className="num-serif" style={{ fontSize: 'clamp(28px, 8vw, 36px)' }}>Inicio</div>
        <div style={{ fontSize: 14, color: 'var(--color-sage)', marginTop: 4, textTransform: 'capitalize' }}>
          {todayLabel()}
        </div>
      </section>

      {/* Instalar app + activar notificaciones */}
      <section style={{ padding: '0 18px 16px' }}>
        <InstallNotifyBanner />
      </section>

      {/* Tu día */}
      <section style={{ padding: '0 18px 20px' }}>
        <div className="cap" style={{ marginBottom: 10 }}>Tu día</div>
        {hoy.length === 0
          ? <EmptyState>Nada agendado para hoy ✨</EmptyState>
          : (
            <div style={{ display: 'grid', gap: 12 }}>
              {hoy.map((item, i) => (
                <Link key={i} to={TIPO_ROUTE[item.tipo] ?? '/'}
                  style={{ display: 'flex', gap: 10, alignItems: 'flex-start', textDecoration: 'none', color: 'inherit' }}>
                  <TipoIcon tipo={item.tipo} />
                  <div style={{ flex: 1 }}>
                    <div style={{ display: 'flex', gap: 8, alignItems: 'baseline' }}>
                      <span style={{ fontSize: 13, color: 'var(--color-sage)', flexShrink: 0 }}>{item.hora}</span>
                      <span style={{ fontSize: 15, fontWeight: 500 }}>{item.titulo}</span>
                    </div>
                    {item.sub && (
                      <div style={{ fontSize: 12, color: 'var(--color-sage)', marginTop: 2 }}>{item.sub}</div>
                    )}
                    {item.avisos && item.avisos.length > 0 && (
                      <div style={{ fontSize: 11.5, color: 'var(--color-voltage-ink, var(--color-sage))', marginTop: 3 }}>
                        🔔 te aviso {item.avisos.join(' · ')}
                      </div>
                    )}
                  </div>
                </Link>
              ))}
            </div>
          )}
      </section>

      {/* Lo que viene */}
      {upcoming.length > 0 && (
        <section style={{ padding: '0 18px 20px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
            <span className="cap">Lo que viene</span>
            <Link to="/agenda" style={{ fontSize: 12, color: 'var(--color-sage)', textDecoration: 'none' }}>Ver agenda →</Link>
          </div>
          <div style={{ display: 'grid', gap: 12 }}>
            {upcoming.map((item) => (
              <Link key={item.id} to="/agenda" style={{ display: 'flex', gap: 10, alignItems: 'flex-start', textDecoration: 'none', color: 'inherit' }}>
                <TipoIcon tipo={item.kind} />
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 12, color: 'var(--color-sage)' }}>{whenLabel(item.when)}</div>
                  <div style={{ fontSize: 15, fontWeight: 500 }}>{item.title}</div>
                </div>
              </Link>
            ))}
          </div>
        </section>
      )}

      {/* Plata mini-card */}
      <div style={{ padding: '0 18px 20px' }}>
        <Link to="/finanzas" style={{ textDecoration: 'none', color: 'inherit' }}>
          <Card>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
              <i className="ti ti-coin" style={{ fontSize: 16, color: 'var(--color-sage)' }} aria-hidden />
              <span className="cap">Plata</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
              <div>
                <div className="cap" style={{ fontSize: 10 }}>Gastado</div>
                <div className="num-serif" style={{ fontSize: 18, marginTop: 2 }}>{formatMoney(k.gasto_mes)}</div>
              </div>
              <div>
                <div className="cap" style={{ fontSize: 10 }}>A pagar</div>
                <div className="num-serif" style={{ fontSize: 18, marginTop: 2 }}>{formatMoney(cicloEnCursoTotal(venc.data, recurring.data))}</div>
              </div>
              <div>
                <div className="cap" style={{ fontSize: 10 }}>Disponible</div>
                <div className="num-serif" style={{ fontSize: 18, marginTop: 2 }}>{formatMoney(k.disponible)}</div>
              </div>
            </div>
            <div style={{ marginTop: 10, fontSize: 12, color: 'var(--color-sage)', textAlign: 'right' }}>Ver finanzas →</div>
          </Card>
        </Link>
      </div>

      {/* Pendientes card */}
      <div style={{ padding: '0 18px 20px' }}>
        <Link to="/tareas" style={{ textDecoration: 'none', color: 'inherit' }}>
          <Card>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <i className="ti ti-checkbox" style={{ fontSize: 16, color: 'var(--color-sage)' }} aria-hidden />
                <span className="cap">Pendientes</span>
              </div>
              {pendientes.length > 0 && (
                <span style={{
                  fontSize: 12, fontWeight: 600, background: 'var(--color-voltage)',
                  color: 'var(--voltage-on-dark)', borderRadius: 20, padding: '2px 10px',
                }}>
                  {pendientes.length}
                </span>
              )}
            </div>
            {pendientes.length === 0
              ? <div style={{ fontSize: 14, color: 'var(--color-sage)' }}>Todo al día</div>
              : (
                <div style={{ display: 'grid', gap: 10 }}>
                  {top3.map((t) => (
                    <div key={t.id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
                      <span style={{ fontSize: 14, flex: 1 }}>{t.text}</span>
                      <PriorityChip priority={t.priority} />
                    </div>
                  ))}
                  {pendientes.length > 3 && (
                    <div style={{ fontSize: 12, color: 'var(--color-sage)' }}>+{pendientes.length - 3} más →</div>
                  )}
                </div>
              )}
          </Card>
        </Link>
      </div>

      {/* Secciones del asistente como cards clickeables */}
      <SectionCard to="/habitos" icon="ti-flame" label="Hábitos" summary={nHab > 0 ? `${nHab} hábito${nHab === 1 ? '' : 's'}` : 'Seguí tus hábitos'} />
      <SectionCard to="/listas" icon="ti-shopping-cart" label="Listas" summary={nList > 0 ? `${nList} lista${nList === 1 ? '' : 's'}` : 'Tus listas de compras'} />
      <SectionCard to="/notas" icon="ti-note" label="Notas" summary={nNot > 0 ? `${nNot} nota${nNot === 1 ? '' : 's'}` : 'Tus notas'} />
    </div>
  )
}
