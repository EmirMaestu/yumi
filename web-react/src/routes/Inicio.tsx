import { Link } from 'react-router-dom'
import { useOverview } from '../hooks/useOverview'
import { useVencimientos } from '../hooks/useVencimientos'
import { useAccountsWithBalances } from '../hooks/useAccounts'
import { useRecurring } from '../hooks/useRecurring'
import { formatMoney, formatUsdApprox } from '../lib/format'
import { enCuotas as calcEnCuotas, aPagarCard, aPagarTotal } from '../lib/cards'
import Card from '../components/ui/Card'
import TickMark from '../components/ui/TickMark'
import StatNumber from '../components/ui/StatNumber'
import CategoryBar from '../components/ui/CategoryBar'
import AlertPill from '../components/ui/AlertPill'
import { InicioSkeleton } from '../components/ui/skeletons'
import EmptyState from '../components/ui/EmptyState'

function daysUntil(dateStr?: string): number | null { if (!dateStr) return null; return Math.ceil((new Date(dateStr).getTime() - Date.now()) / 86_400_000) }

export default function Inicio() {
  const { data, isLoading, isError } = useOverview()
  const venc = useVencimientos()
  const accounts = useAccountsWithBalances()
  const recurring = useRecurring()

  if (isLoading) return <InicioSkeleton />
  if (isError || !data) return <EmptyState>No pudimos cargar tus datos. Reintentá.</EmptyState>
  const k = data.kpis
  const delta = k.gasto_mes - k.gasto_prev_alt
  const maxCat = Math.max(1, ...data.por_categoria.map((c) => c.total))

  // Credit cards from accounts-with-balances, matched with vencimientos
  const creditCards = accounts.data?.filter((a) => a.type === 'credito') ?? []

  // Aggregate deuda total and enCuotas across all credit cards
  const totalAPagar = aPagarTotal(venc.data)
  const totalEnCuotas = creditCards.reduce((s, card) => s + calcEnCuotas(card.id, recurring.data), 0)

  return (
    <div style={{ padding: '8px 4px 24px' }}>
      <section style={{ padding: '8px 18px 6px' }}>
        <div className="cap">Gastado este mes</div>
        <div className="num-serif" style={{ fontSize: 'clamp(44px, 13vw, 56px)', marginTop: 8 }}>{formatMoney(k.gasto_mes)}</div>
        <div style={{ fontSize: 13, color: 'var(--color-sage)', marginTop: 6 }}>{delta >= 0 ? '▲' : '▼'} {formatMoney(Math.abs(delta))} vs mes pasado</div>
        <div style={{ marginTop: 16 }}><TickMark /></div>
      </section>
      <section style={{ display: 'flex', gap: 6, padding: '16px 18px 6px' }}>
        <StatNumber label="Ingresos">{formatMoney(k.ingreso_mes)}</StatNumber>
        <StatNumber label="Patrimonio">{formatMoney(data.patrimonio_ars)}</StatNumber>
        <StatNumber label="En cuotas">{formatMoney(totalEnCuotas)}</StatNumber>
      </section>
      <div style={{ padding: '12px 18px 0' }}>
        <Card>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: 15, fontWeight: 500 }}><i className="ti ti-credit-card" style={{ marginRight: 7 }} aria-hidden />Cuotas y tarjetas</span>
          </div>
          {/* PRIMARY: A pagar este mes — sum of ciclo cerrado (lo que vence) */}
          <div style={{ marginTop: 14 }}>
            <div className="cap">A pagar este mes</div>
            <div className="num-serif" style={{ fontSize: 32, marginTop: 4 }}>{formatMoney(totalAPagar)}</div>
            <div style={{ fontSize: 12, color: 'var(--color-sage)', marginTop: 4 }}>En cuotas (deuda futura): {formatMoney(totalEnCuotas)}</div>
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
                  <span className="num-serif" style={{ fontSize: 15, fontWeight: 500 }}>{formatMoney(aPagar)}</span>
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
          : data.por_categoria.slice(0, 6).map((c) => <CategoryBar key={c.cat} label={c.cat} total={c.total} max={maxCat} />)}
      </section>
      {formatUsdApprox(data.patrimonio_ars, data.blue) && (
        <div style={{ padding: '0 18px', fontSize: 12, color: 'var(--color-sage)' }}>Patrimonio {formatUsdApprox(data.patrimonio_ars, data.blue)} · blue {formatMoney(data.blue)}</div>
      )}
    </div>
  )
}
