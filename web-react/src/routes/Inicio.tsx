import { type CSSProperties } from 'react'
import { Link, useNavigate, useOutletContext } from 'react-router-dom'
import { type LayoutCtx } from '../components/nav/AppLayout'
import { useOverview } from '../hooks/useOverview'
import { useVencimientos } from '../hooks/useVencimientos'
import { useAccountsWithBalances } from '../hooks/useAccounts'
import { useRecurring } from '../hooks/useRecurring'
import { useCategories } from '../hooks/useCategories'
import { useBudgets, budgetPct, budgetColor } from '../hooks/useBudgets'
import { useSplitsSummary } from '../hooks/useSplits'
import { formatMoney, formatUsdApprox } from '../lib/format'
import { Money } from '../lib/privacy'
import { enCuotas as calcEnCuotas, cicloEnCursoTotal, aPagarCard, aPagarTotal } from '../lib/cards'
import Card from '../components/ui/Card'
import TickMark from '../components/ui/TickMark'
import StatNumber from '../components/ui/StatNumber'
import CategoryBar from '../components/ui/CategoryBar'
import AlertPill from '../components/ui/AlertPill'
import { InicioSkeleton } from '../components/ui/skeletons'
import EmptyState from '../components/ui/EmptyState'
import SectionCard from '../components/ui/SectionCard'

function daysUntil(dateStr?: string): number | null { if (!dateStr) return null; return Math.ceil((new Date(dateStr).getTime() - Date.now()) / 86_400_000) }

export default function Inicio() {
  const ctx = useOutletContext<LayoutCtx | null>()
  const openAdd = ctx?.openAdd ?? (() => {})
  const nav = useNavigate()
  const { data, isLoading, isError } = useOverview()
  const venc = useVencimientos()
  const accounts = useAccountsWithBalances()
  const recurring = useRecurring()
  const cats = useCategories()
  const budgets = useBudgets()
  const splits = useSplitsSummary()

  if (isLoading) return <InicioSkeleton />
  if (isError || !data) return <EmptyState>No pudimos cargar tus datos. Reintentá.</EmptyState>
  const k = data.kpis
  const delta = k.gasto_mes - k.gasto_prev_alt
  const maxCat = Math.max(1, ...data.por_categoria.map((c) => c.total))

  // Credit cards from accounts-with-balances, matched with vencimientos
  const creditCards = accounts.data?.filter((a) => a.type === 'credito') ?? []

  // Aggregate deuda total and enCuotas across all credit cards
  const totalEnCurso = cicloEnCursoTotal(venc.data, recurring.data)
  const totalAPagar = aPagarTotal(venc.data)
  const totalEnCuotas = creditCards.reduce((s, card) => s + calcEnCuotas(card.id, recurring.data), 0)
  const nCuentas = accounts.data?.length ?? 0
  const nCats = cats.data?.length ?? 0
  const nRec = recurring.data?.length ?? 0

  return (
    <div style={{ padding: '8px 4px 24px' }}>
      <section style={{ padding: '8px 18px 6px' }}>
        <Link to="/movimientos?type=gasto" style={{ textDecoration: 'none', color: 'inherit', display: 'block' }}>
          <div className="cap">Gastado este mes</div>
          <div className="num-serif" style={{ fontSize: 'clamp(44px, 13vw, 56px)', marginTop: 8 }}><Money value={k.gasto_mes} /></div>
        </Link>
        <div style={{ fontSize: 13, color: 'var(--color-sage)', marginTop: 6 }}>{delta >= 0 ? '▲' : '▼'} <Money value={Math.abs(delta)} /> vs mes pasado a esta altura</div>
        {(data.dia ?? 0) >= 5 && k.proyeccion_fin_mes != null && (
          <div style={{ fontSize: 13, color: 'var(--color-sage)', marginTop: 4 }}>A este ritmo: ~<Money value={k.proyeccion_fin_mes} /> este mes</div>
        )}
        <div style={{ marginTop: 16 }}><TickMark /></div>
      </section>
      {/* Acciones del número grande (mismo patrón que el home) */}
      <section style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8, padding: '16px 18px 4px' }}>
        <ActionTile icon="ti-plus" label="Cargar gasto" onClick={() => openAdd('gasto')} />
        <ActionTile icon="ti-plus" label="Ingreso" onClick={() => openAdd('gasto')} />
        <ActionTile icon="ti-credit-card" label="Pagar tarjeta" onClick={() => nav('/tarjetas')} />
      </section>
      {(k.anomalias?.length ?? 0) > 0 && (
        <div style={{ padding: '4px 18px 0' }}>
          <Card>
            <div className="cap" style={{ marginBottom: 8 }}>Gastos inusuales</div>
            {k.anomalias!.map((a) => (
              <Link key={a.tx_id} to="/movimientos" style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13, padding: '4px 0', textDecoration: 'none', color: 'inherit' }}>
                <span style={{ flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{a.description}</span>
                <span style={{ marginLeft: 8 }}><Money value={a.amount} /></span>
              </Link>
            ))}
          </Card>
        </div>
      )}
      <section style={{ display: 'flex', gap: 6, padding: '16px 18px 6px' }}>
        <StatNumber label="Ingresos" to="/movimientos?type=ingreso"><Money value={k.ingreso_mes} /></StatNumber>
        <StatNumber label="Patrimonio (tuyo)" to="/cuentas"><Money value={data.patrimonio_ars} /></StatNumber>
        <StatNumber label="En cuotas" to="/recurrentes"><Money value={totalEnCuotas} /></StatNumber>
      </section>
      <div style={{ padding: '12px 18px 0' }}>
        <Card>
          <Link to="/tarjetas" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', textDecoration: 'none', color: 'inherit' }}>
            <span style={{ fontSize: 15, fontWeight: 500 }}><i className="ti ti-credit-card" style={{ marginRight: 7 }} aria-hidden />Cuotas y tarjetas</span>
            <i className="ti ti-chevron-right" style={{ fontSize: 16, color: 'var(--color-sage)' }} aria-hidden />
          </Link>
          {/* PRIMARY: resumen a pagar (lo exigible); próximo resumen como proyección rotulada */}
          <div style={{ marginTop: 14 }}>
            <div className="cap">Resumen a pagar</div>
            <div className="num-serif" style={{ fontSize: 32, marginTop: 4 }}><Money value={totalAPagar} /></div>
            <div style={{ fontSize: 12, color: 'var(--color-sage)', marginTop: 4 }}>Próximo resumen: <Money value={totalEnCurso} /></div>
            <Link to="/recurrentes" style={{ fontSize: 12, color: 'var(--color-sage)', marginTop: 2, display: 'inline-block', textDecoration: 'none' }}>En cuotas (deuda futura): <Money value={totalEnCuotas} /> →</Link>
          </div>
          <div style={{ height: 1, background: 'var(--color-mist)', margin: '16px 0' }} />
          {/* Per-card rows */}
          {(accounts.isLoading || venc.isLoading) && <span aria-hidden className="nf-skel" style={{ height: 48, display: 'block' }} />}
          {creditCards.length === 0 && !accounts.isLoading && <EmptyState>Sin tarjetas de crédito.</EmptyState>}
          {creditCards.map((card) => {
            const v = venc.data?.find((x) => x.account_id === card.id)
            const aPagar = aPagarCard(v)
            const dias = daysUntil(v?.next_closing)
            return (
              <Link
                key={card.id}
                to={`/tarjetas/${card.id}`}
                style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12, textDecoration: 'none', color: 'inherit', cursor: 'pointer' }}
              >
                <span>
                  <span style={{ fontSize: 14, fontWeight: 500 }}>{card.name}</span><br />
                  {v && dias !== null && dias >= 0 && dias <= 5
                    ? <AlertPill>cierra en {dias} día{dias === 1 ? '' : 's'}</AlertPill>
                    : v?.next_closing
                      ? <span style={{ fontSize: 11, color: 'var(--color-sage)' }}>cierra {v.next_closing.slice(8, 10)}/{v.next_closing.slice(5, 7)}</span>
                      : null}
                </span>
                <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span className="num-serif" style={{ fontSize: 15, fontWeight: 500 }}><Money value={aPagar} /></span>
                  <i className="ti ti-chevron-right" style={{ fontSize: 16, color: 'var(--color-sage)' }} aria-hidden />
                </span>
              </Link>
            )
          })}
        </Card>
      </div>
      <section style={{ padding: '20px 18px 8px' }}>
        <div className="cap" style={{ marginBottom: 12 }}>Gastos por categoría</div>
        {data.por_categoria.length === 0
          ? <EmptyState>Todavía no cargaste gastos este mes — escribile al bot o tocá +.</EmptyState>
          : data.por_categoria.slice(0, 6).map((c) => {
            const catId = cats.data?.find((x) => x.name === c.cat)?.id
            return <CategoryBar key={c.cat} label={c.cat} total={c.total} max={maxCat} to={catId ? `/movimientos?category_id=${catId}` : '/movimientos'} />
          })}
      </section>

      {/* Presupuestos: top 3 por % usado */}
      {(budgets.data?.length ?? 0) > 0 && (
        <div style={{ padding: '4px 18px 0' }}>
          <Card>
            <Link to="/presupuestos" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', textDecoration: 'none', color: 'inherit' }}>
              <span style={{ fontSize: 15, fontWeight: 500 }}><i className="ti ti-target" style={{ marginRight: 7 }} aria-hidden />Presupuestos</span>
              <span style={{ fontSize: 12, color: 'var(--color-sage)' }}>Ver todos →</span>
            </Link>
            <div style={{ marginTop: 12, display: 'grid', gap: 10 }}>
              {[...budgets.data!].sort((a, b) => budgetPct(b) - budgetPct(a)).slice(0, 3).map((b) => {
                const pct = budgetPct(b)
                return (
                  <div key={b.id}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12.5, marginBottom: 4 }}>
                      <span>{b.icon ? `${b.icon} ` : ''}{b.name}</span>
                      <span style={{ color: 'var(--color-sage)' }}><Money value={b.spent} /> / <Money value={b.amount} /></span>
                    </div>
                    <div style={{ height: 7, borderRadius: 5, background: 'var(--color-mist)', overflow: 'hidden' }}>
                      <div style={{ width: `${Math.min(100, pct)}%`, height: '100%', background: budgetColor(pct) }} />
                    </div>
                  </div>
                )
              })}
            </div>
          </Card>
        </div>
      )}

      {/* Splits de pareja (solo hogares de >1; read-only) */}
      {splits.isSuccess && splits.data && (
        <div style={{ padding: '4px 18px 0' }}>
          <Card>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: 14, fontWeight: 500 }}>Con {splits.data.other_name}</span>
              <span style={{ fontSize: 15, fontWeight: 500, color: splits.data.status === 'you_owe' ? 'var(--color-error)' : splits.data.status === 'they_owe' ? '#3b6d11' : 'var(--color-sage)' }}>
                {splits.data.status === 'even' ? 'Están a mano 🤝'
                  : splits.data.status === 'they_owe' ? <>🟢 Te debe <Money value={splits.data.amount} /></>
                    : <>🔴 Le debés <Money value={splits.data.amount} /></>}
              </span>
            </div>
            <div style={{ fontSize: 11, color: 'var(--color-sage)', marginTop: 4 }}>Gestionalo desde el bot</div>
          </Card>
        </div>
      )}

      {/* Secciones de finanzas como cards clickeables */}
      <section style={{ padding: '12px 18px 6px' }}>
        <div className="cap">Secciones</div>
      </section>
      <SectionCard to="/movimientos" icon="ti-arrows-left-right" label="Movimientos" summary="Buscar y filtrar tus gastos e ingresos" />
      <SectionCard to="/tarjetas" icon="ti-credit-card" label="Tarjetas" summary={`${creditCards.length} tarjeta${creditCards.length === 1 ? '' : 's'} de crédito`} />
      <SectionCard to="/cuentas" icon="ti-wallet" label="Cuentas" summary={`${nCuentas} cuenta${nCuentas === 1 ? '' : 's'}`} />
      <SectionCard to="/presupuestos" icon="ti-target" label="Presupuestos" summary={`${budgets.data?.length ?? 0} presupuesto${(budgets.data?.length ?? 0) === 1 ? '' : 's'}`} />
      <SectionCard to="/categorias" icon="ti-tags" label="Categorías" summary={`${nCats} categoría${nCats === 1 ? '' : 's'}`} />
      <SectionCard to="/recurrentes" icon="ti-repeat" label="Recurrentes" summary={`${nRec} recurrente${nRec === 1 ? '' : 's'}`} />

      {(data.unconverted?.length ?? 0) > 0 && (
        <div style={{ margin: '4px 18px 0', padding: '8px 12px', borderRadius: 10, background: '#fff3cd', color: '#7a5c00', fontSize: 12 }}>
          {data.unconverted!.map((u) => `${u.currency} ${Math.abs(u.amount).toLocaleString('es-AR')}`).join(' · ')} sin convertir — no hay cotización
        </div>
      )}
      {formatUsdApprox(data.patrimonio_ars, data.blue) && (
        <div style={{ padding: '0 18px', fontSize: 12, color: 'var(--color-sage)' }}>
          Patrimonio {formatUsdApprox(data.patrimonio_ars, data.blue)} · blue {formatMoney(data.blue)}
          {data.blue_at ? ` · ${new Date(data.blue_at * 1000).toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit' })}` : ''}
        </div>
      )}
    </div>
  )
}

// Acción del número grande: tile verde tenue (idéntico lenguaje al home).
function ActionTile({ icon, label, onClick }: { icon: string; label: string; onClick: () => void }) {
  return (
    <button onClick={onClick} style={actionTile}>
      <i className={`ti ${icon}`} style={{ fontSize: 20, color: 'var(--color-voltage-ink, #1f7a2e)' }} aria-hidden />
      <span style={{ fontSize: 11.5, fontWeight: 600, color: 'var(--color-voltage-ink, #1f7a2e)', textAlign: 'center' }}>{label}</span>
    </button>
  )
}

const actionTile: CSSProperties = {
  background: 'rgba(43,238,75,0.12)', border: 'none', borderRadius: 13, padding: '11px 6px',
  display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6, cursor: 'pointer', font: 'inherit',
}
