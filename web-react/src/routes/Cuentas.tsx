import { useAccountsWithBalances } from '../hooks/useAccounts'
import { formatMoney } from '../lib/format'
import Card from '../components/ui/Card'
import Skeleton from '../components/ui/Skeleton'
import EmptyState from '../components/ui/EmptyState'
const TYPE_LABEL: Record<string, string> = { efectivo: 'Efectivo', billetera: 'Billetera', credito: 'Crédito', banco: 'Banco', inversion: 'Inversión' }
export default function Cuentas() {
  const { data, isLoading } = useAccountsWithBalances()
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
