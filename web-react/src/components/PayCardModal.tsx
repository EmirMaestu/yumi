import { useState } from 'react'
import Modal from './ui/Modal'
import Select from './ui/Select'
import { useAccountsWithBalances } from '../hooks/useAccounts'
import { useTransferMutation } from '../hooks/useTransactions'
import { parseAmount } from '../lib/parseAmount'
import { formatMoney, todayISODate, dateToNoonISO } from '../lib/format'

// Flujo "Registrar pago" de tarjeta (BF2/D9): transferencia desde una cuenta
// no-crédito hacia la tarjeta. Baja la deuda derivada sin tocar KPIs.
export default function PayCardModal({ card, defaultAmount, open, onClose }: {
  card: { id: number; name: string }
  defaultAmount: number
  open: boolean
  onClose: () => void
}) {
  const accounts = useAccountsWithBalances()
  const transfer = useTransferMutation('Pago registrado — tu deuda se actualizó')

  const [fromId, setFromId] = useState<string | undefined>(undefined)
  const [amount, setAmount] = useState(defaultAmount > 0 ? String(defaultAmount) : '')
  const [date, setDate] = useState(todayISODate())
  const [error, setError] = useState('')

  const fromOpts = (accounts.data ?? [])
    .filter((a) => a.type !== 'credito' && a.id !== card.id)
    .map((a) => ({ value: String(a.id), label: a.name }))

  function handleSave() {
    if (!fromId) { setError('Elegí la cuenta desde la que pagás'); return }
    const monto = parseAmount(amount)
    if (isNaN(monto) || monto <= 0) { setError('Ingresá un monto válido'); return }
    transfer.mutate({
      from_account_id: Number(fromId),
      to_account_id: card.id,
      amount: monto,
      occurred_at: dateToNoonISO(date),
    }, { onSuccess: onClose })
  }

  return (
    <Modal open={open} onClose={onClose} title={`Pagar ${card.name}`}>
      <div style={{ display: 'grid', gap: 14 }}>
        <label style={labelStyle}>
          Pagar desde
          <Select
            value={fromId}
            onValueChange={(v) => { setFromId(v); if (error) setError('') }}
            options={fromOpts}
            placeholder="Elegí una cuenta…"
            ariaLabel="Cuenta de origen"
            style={{ width: '100%' }}
          />
        </label>
        <label style={labelStyle}>
          Monto
          <input
            inputMode="decimal"
            value={amount}
            onChange={(e) => { setAmount(e.target.value); if (error) setError('') }}
            placeholder="0"
            style={inputStyle}
          />
          {defaultAmount > 0 && (
            <span style={{ fontSize: 12, color: 'var(--color-sage)' }}>
              Resumen a pagar: {formatMoney(defaultAmount)}
            </span>
          )}
        </label>
        <label style={labelStyle}>
          Fecha
          <input type="date" value={date} onChange={(e) => setDate(e.target.value)} style={inputStyle} />
        </label>
        {error && <span style={{ fontSize: 12, color: 'var(--color-error)' }}>{error}</span>}
        <div style={{ display: 'flex', gap: 8 }}>
          <button onClick={onClose} style={ghostBtn}>Cancelar</button>
          <button onClick={handleSave} style={ctaBtn} disabled={transfer.isPending}>
            {transfer.isPending ? 'Registrando…' : 'Registrar pago'}
          </button>
        </div>
      </div>
    </Modal>
  )
}

const labelStyle: React.CSSProperties = { display: 'grid', gap: 4, fontSize: 13, color: 'var(--color-sage)' }
const inputStyle: React.CSSProperties = {
  border: '1px solid var(--color-mist)', borderRadius: 10, padding: '10px 12px',
  fontSize: 14, background: 'var(--color-linen)', width: '100%', boxSizing: 'border-box',
}
const ghostBtn: React.CSSProperties = {
  flex: 1, background: 'transparent', border: '1px solid var(--color-mist)',
  borderRadius: 10, padding: '12px 14px', fontSize: 13, cursor: 'pointer',
}
const ctaBtn: React.CSSProperties = {
  flex: 2, background: 'var(--color-voltage)', color: 'var(--voltage-on-dark)',
  border: 'none', borderRadius: 10, padding: '12px 14px', fontWeight: 500, cursor: 'pointer',
}
