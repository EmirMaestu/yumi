import Sheet from './ui/Sheet'
import Select from './ui/Select'
import { useCategories } from '../hooks/useCategories'
import { useTxMutations } from '../hooks/useTransactions'
import { Money } from '../lib/privacy'
import { dateToNoonISO, todayISODate } from '../lib/format'
import { type Transaction } from '../lib/types'

const KIND_LABEL: Record<string, string> = { transfer: 'Transferencia', card_payment: 'Pago de tarjeta', adjustment: 'Ajuste' }

export default function TxDetailSheet({ tx, open, onClose, onEdit }: {
  tx: Transaction | null
  open: boolean
  onClose: () => void
  onEdit: (tx: Transaction) => void
}) {
  const categories = useCategories()
  const { update, create, remove } = useTxMutations()
  if (!tx) return null

  const isTransfer = tx.kind === 'transfer' || tx.kind === 'card_payment'
  const isSpecial = isTransfer || tx.kind === 'adjustment'
  const categoryOpts = (categories.data ?? []).map((c) => ({ value: String(c.id), label: c.name }))

  const duplicate = () => {
    create.mutate({
      type: tx.type, amount: tx.amount, currency: tx.currency, account_id: tx.account_id,
      category_id: tx.category_id ?? undefined, description: tx.description,
      occurred_at: dateToNoonISO(todayISODate()),
    }, { onSuccess: onClose })
  }

  return (
    <Sheet open={open} onClose={onClose} title="Detalle del movimiento">
      <div style={{ display: 'grid', gap: 14 }}>
        <div>
          <div className="num-serif" style={{ fontSize: 34, color: tx.type === 'ingreso' ? '#3b6d11' : 'var(--color-obsidian-ink)' }}>
            {tx.type === 'ingreso' ? '+' : '−'}<Money value={tx.amount} currency={tx.currency} />
          </div>
          <div style={{ fontSize: 15, fontWeight: 500, marginTop: 4 }}>{tx.description}</div>
          {tx.kind && KIND_LABEL[tx.kind] && (
            <span style={{ display: 'inline-block', marginTop: 6, fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', padding: '2px 8px', borderRadius: 9999, background: 'var(--color-mist)', color: 'var(--color-sage)' }}>
              {KIND_LABEL[tx.kind]}
            </span>
          )}
        </div>

        <Row label="Tipo" value={tx.type === 'ingreso' ? 'Ingreso' : 'Gasto'} />
        {!isSpecial && (
          <div style={{ display: 'grid', gap: 4 }}>
            <span style={labelStyle}>Categoría</span>
            <Select
              value={tx.category_id ? String(tx.category_id) : undefined}
              onValueChange={(v) => update.mutate({ id: tx.id, category_id: Number(v) })}
              options={categoryOpts} placeholder="Sin categoría…" ariaLabel="Categoría" style={{ width: '100%' }} />
          </div>
        )}
        <Row label="Cuenta" value={tx.acc_name ?? tx.account_name ?? '—'} />
        <Row label="Fecha" value={tx.occurred_at.slice(0, 10)} />
        {tx.owner_name && <Row label="Cargado por" value={tx.owner_name} />}

        <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
          {!isSpecial && <button onClick={() => { onEdit(tx); onClose() }} style={ghostBtn}>Editar</button>}
          {!isSpecial && <button onClick={duplicate} style={ghostBtn}>Duplicar</button>}
          <button onClick={() => { remove.mutate(tx.id); onClose() }} style={dangerBtn}>Borrar</button>
        </div>
      </div>
    </Sheet>
  )
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 14 }}>
      <span style={labelStyle}>{label}</span>
      <span>{value}</span>
    </div>
  )
}

const labelStyle: React.CSSProperties = { fontSize: 13, color: 'var(--color-sage)' }
const ghostBtn: React.CSSProperties = { flex: 1, background: 'transparent', border: '1px solid var(--color-mist)', borderRadius: 10, padding: '11px', fontSize: 13, cursor: 'pointer' }
const dangerBtn: React.CSSProperties = { flex: 1, background: 'transparent', border: '1px solid var(--color-error)', color: 'var(--color-error)', borderRadius: 10, padding: '11px', fontSize: 13, cursor: 'pointer' }
