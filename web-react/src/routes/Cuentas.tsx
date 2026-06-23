import { useState } from 'react'
import { useForm, Controller } from 'react-hook-form'
import { useAccountsWithBalances, useAccountMutations } from '../hooks/useAccounts'
import { type Account } from '../lib/types'
import { formatMoney } from '../lib/format'
import Card from '../components/ui/Card'
import Skeleton from '../components/ui/Skeleton'
import EmptyState from '../components/ui/EmptyState'
import Modal from '../components/ui/Modal'
import ConfirmDialog from '../components/ui/ConfirmDialog'
import Select from '../components/ui/Select'

const TYPE_LABEL: Record<string, string> = { efectivo: 'Efectivo', billetera: 'Billetera', credito: 'Crédito', banco: 'Banco', inversion: 'Inversión' }
const TYPE_OPTS = [
  { value: 'efectivo', label: 'Efectivo' },
  { value: 'billetera', label: 'Billetera' },
  { value: 'credito', label: 'Crédito' },
  { value: 'banco', label: 'Banco' },
  { value: 'inversion', label: 'Inversión' },
]

interface AccountForm { name: string; type: Account['type'] }

function AccountFormModal({ open, onClose, initial, onSubmit, title }: {
  open: boolean
  onClose: () => void
  initial?: AccountForm
  onSubmit: (data: AccountForm) => void
  title: string
}) {
  const { register, handleSubmit, control, reset } = useForm<AccountForm>({
    defaultValues: initial ?? { name: '', type: 'banco' },
  })
  const submit = (data: AccountForm) => { onSubmit(data); reset() }
  return (
    <Modal open={open} onClose={() => { onClose(); reset() }} title={title}>
      <form onSubmit={handleSubmit(submit)} style={{ display: 'grid', gap: 12 }}>
        <input
          {...register('name', { required: true })}
          placeholder="Nombre de la cuenta"
          style={inputStyle}
        />
        <Controller
          name="type"
          control={control}
          render={({ field }) => (
            <Select
              value={field.value}
              onValueChange={(v) => field.onChange(v)}
              options={TYPE_OPTS}
              ariaLabel="Tipo de cuenta"
              style={{ width: '100%' }}
            />
          )}
        />
        <button type="submit" style={ctaBtn}>Guardar</button>
      </form>
    </Modal>
  )
}

export default function Cuentas() {
  const { data, isLoading } = useAccountsWithBalances()
  const { create, update, remove } = useAccountMutations()

  const [createOpen, setCreateOpen] = useState(false)
  const [editAccount, setEditAccount] = useState<Account | null>(null)
  const [deleteAccount, setDeleteAccount] = useState<Account | null>(null)

  if (isLoading) return <div style={{ padding: 18 }}><Skeleton h={80} /></div>

  return (
    <div style={{ padding: '14px 18px 24px', display: 'grid', gap: 12 }}>
      <div style={{ display: 'flex', alignItems: 'center' }}>
        <div className="cap" style={{ flex: 1 }}>Cuentas</div>
        <button onClick={() => setCreateOpen(true)} style={ghostBtn}>+ Nueva cuenta</button>
      </div>

      {(!data || data.length === 0) && <EmptyState>No tenés cuentas cargadas.</EmptyState>}

      {data?.map((a) => (
        <Card key={a.id}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
            <span style={{ fontSize: 15, fontWeight: 500 }}>{a.name}</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span className="cap" style={{ fontSize: 10.5 }}>{TYPE_LABEL[a.type] ?? a.type}</span>
              <button aria-label={`Editar ${a.name}`} onClick={() => setEditAccount(a)} style={iconBtn}>
                <i className="ti ti-edit" aria-hidden />
              </button>
              <button aria-label={`Borrar ${a.name}`} onClick={() => setDeleteAccount(a)} style={iconBtn}>
                <i className="ti ti-trash" aria-hidden />
              </button>
            </div>
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

      {/* Create modal */}
      <AccountFormModal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        title="Nueva cuenta"
        onSubmit={(data) => { create.mutate(data); setCreateOpen(false) }}
      />

      {/* Edit modal */}
      <AccountFormModal
        open={editAccount !== null}
        onClose={() => setEditAccount(null)}
        initial={editAccount ? { name: editAccount.name, type: editAccount.type } : undefined}
        title="Editar cuenta"
        onSubmit={(data) => {
          if (editAccount) update.mutate({ id: editAccount.id, ...data })
          setEditAccount(null)
        }}
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
    </div>
  )
}

const iconBtn: React.CSSProperties = { background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-sage)', fontSize: 16, padding: 2 }
const ghostBtn: React.CSSProperties = { background: 'transparent', border: '1px solid var(--color-mist)', borderRadius: 10, padding: '7px 14px', fontSize: 13, cursor: 'pointer' }
const ctaBtn: React.CSSProperties = { background: 'var(--color-voltage)', color: 'var(--voltage-on-dark)', border: 'none', borderRadius: 10, padding: '14px', fontWeight: 500, cursor: 'pointer' }
const inputStyle: React.CSSProperties = { border: '1px solid var(--color-mist)', borderRadius: 10, padding: '10px 12px', fontSize: 14, background: 'var(--color-linen)', width: '100%', boxSizing: 'border-box' }
