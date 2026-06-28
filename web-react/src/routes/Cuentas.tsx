import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { apiPost } from '../lib/api'
import { useAccountsWithBalances, useAccountMutations } from '../hooks/useAccounts'
import { useRecurring } from '../hooks/useRecurring'
import { type Account } from '../lib/types'
import { arsBalance, enCuotas, deudaTotal } from '../lib/cards'
import { formatMoney } from '../lib/format'
import Card from '../components/ui/Card'
import { CuentasSkeleton } from '../components/ui/skeletons'
import EmptyState from '../components/ui/EmptyState'
import ConfirmDialog from '../components/ui/ConfirmDialog'
import CardActions from '../components/ui/CardActions'
import AccountForm from '../components/AccountForm'
import AdjustBalanceModal from '../components/AdjustBalanceModal'

const TYPE_LABEL: Record<string, string> = {
  efectivo: 'Efectivo',
  billetera: 'Billetera',
  debito: 'Débito',
  credito: 'Crédito',
  banco: 'Banco',
  dolares: 'Dólares (USD)',
  cripto: 'Cripto',
  inversion: 'Inversión',
}

export default function Cuentas() {
  const { data, isLoading } = useAccountsWithBalances()
  const recurring = useRecurring()
  const { remove } = useAccountMutations()
  const qc = useQueryClient()
  const toggleShared = async (a: Account) => {
    await apiPost('/api/share', { entity: 'accounts', id: a.id, shared: a.shared ? 0 : 1 })
    qc.invalidateQueries()
  }

  const [createOpen, setCreateOpen] = useState(false)
  const [editAccount, setEditAccount] = useState<Account | null>(null)
  const [deleteAccount, setDeleteAccount] = useState<Account | null>(null)
  const [adjustAccount, setAdjustAccount] = useState<Account | null>(null)

  if (isLoading) return <CuentasSkeleton />

  return (
    <div style={{ padding: '14px 18px 24px', display: 'grid', gap: 12 }}>
      <div style={{ display: 'flex', alignItems: 'center' }}>
        <div className="cap" style={{ flex: 1 }}>Cuentas</div>
        <button onClick={() => setCreateOpen(true)} style={ghostBtn}>+ Nueva cuenta</button>
      </div>

      {(!data || data.length === 0) && <EmptyState>No tenés cuentas cargadas.</EmptyState>}

      {data?.map((a) => (
        <Card key={a.id}>
          {/* Header: name left, actions right */}
          <div style={{ display: 'flex', alignItems: 'center' }}>
            <span style={{ fontSize: 15, fontWeight: 500, flex: 1 }}>{a.name}</span>
            <CardActions
              onEdit={() => setEditAccount(a)}
              onDelete={() => setDeleteAccount(a)}
            />
          </div>
          {/* Secondary meta below name */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span className="cap" style={{ fontSize: 10.5 }}>{TYPE_LABEL[a.type] ?? a.type}</span>
            <button onClick={() => toggleShared(a)} title="Privada solo vos / Compartida con tu pareja"
              style={a.shared ? sharedPill : privatePill}>
              {a.shared ? '👥 Compartida' : '🔒 Privada'}
            </button>
          </div>

          {a.type === 'credito' ? (
            /* Credit account: show deuda total with breakdown */
            <div style={{ marginTop: 10, display: 'grid', gap: 4 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                <span style={{ fontSize: 12, color: 'var(--color-sage)' }}>Deuda</span>
                <span className="num-serif" style={{ fontSize: 20 }}>{formatMoney(deudaTotal(a.id, a, recurring.data))}</span>
              </div>
              <div style={{ fontSize: 11, color: 'var(--color-sage)' }}>
                Consumos {formatMoney(Math.abs(arsBalance(a)))} · En cuotas {formatMoney(enCuotas(a.id, recurring.data))}
              </div>
            </div>
          ) : (
            /* Non-credit account: standard balance display */
            <div style={{ marginTop: 10, display: 'grid', gap: 4 }}>
              {(a.balances ?? []).length === 0 && (
                <span style={{ fontSize: 13, color: 'var(--color-sage)' }}>Sin movimientos</span>
              )}
              {a.balances?.map((b) => (
                <div key={b.currency} style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ fontSize: 12, color: 'var(--color-sage)' }}>{b.currency}</span>
                  <span className="num-serif" style={{ fontSize: 20 }}>{formatMoney(b.balance, b.currency)}</span>
                </div>
              ))}
            </div>
          )}

          <button
            onClick={(e) => { e.stopPropagation(); setAdjustAccount(a) }}
            style={adjustBtn}
          >
            Ajustar saldo
          </button>
        </Card>
      ))}

      {/* Create modal */}
      <AccountForm open={createOpen} onClose={() => setCreateOpen(false)} />

      {/* Edit modal */}
      <AccountForm
        key={editAccount ? `acc-${editAccount.id}` : 'acc-edit'}
        account={editAccount}
        open={editAccount !== null}
        onClose={() => setEditAccount(null)}
      />

      {/* Delete confirm */}
      <ConfirmDialog
        open={deleteAccount !== null}
        onOpenChange={(o) => { if (!o) setDeleteAccount(null) }}
        title="¿Borrar esta cuenta?"
        description={deleteAccount ? `Se eliminará "${deleteAccount.name}".` : ''}
        onConfirm={() => {
          if (deleteAccount) remove.mutate(deleteAccount.id)
          setDeleteAccount(null)
        }}
      />

      {/* Adjust balance modal */}
      {adjustAccount && (
        <AdjustBalanceModal
          account={adjustAccount}
          open={adjustAccount !== null}
          onClose={() => setAdjustAccount(null)}
        />
      )}
    </div>
  )
}

const ghostBtn: React.CSSProperties = {
  background: 'transparent',
  border: '1px solid var(--color-mist)',
  borderRadius: 10,
  padding: '7px 14px',
  fontSize: 13,
  cursor: 'pointer',
}
const privatePill: React.CSSProperties = {
  background: 'var(--color-mist)', color: 'var(--color-sage)', border: 'none',
  borderRadius: 9999, padding: '2px 8px', fontSize: 10.5, cursor: 'pointer', font: 'inherit',
}
const sharedPill: React.CSSProperties = {
  ...privatePill, background: 'var(--color-voltage)', color: 'var(--voltage-on-dark)',
}
const adjustBtn: React.CSSProperties = {
  background: 'transparent',
  border: 'none',
  padding: '6px 0 0',
  fontSize: 12,
  color: 'var(--color-sage)',
  cursor: 'pointer',
  textAlign: 'left',
  textDecoration: 'underline',
  textDecorationStyle: 'dotted',
}
