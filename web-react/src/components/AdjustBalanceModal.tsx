import { useState } from 'react'
import Modal from './ui/Modal'
import Select from './ui/Select'
import { useTxMutations } from '../hooks/useTransactions'
import { formatMoney } from '../lib/format'
import { parseAmount } from '../lib/parseAmount'
import { type Balance, type Currency } from '../lib/types'

interface Props {
  account: { id: number; name: string; balances?: Balance[] }
  open: boolean
  onClose: () => void
}

export default function AdjustBalanceModal({ account, open, onClose }: Props) {
  const balances = account.balances ?? []
  const defaultCurrency = balances[0]?.currency ?? 'ARS'

  const [currency, setCurrency] = useState<Currency>(defaultCurrency)
  const [newBalance, setNewBalance] = useState('')
  const [error, setError] = useState('')

  const { create } = useTxMutations()

  const currentBalance = balances.find((b) => b.currency === currency)?.balance ?? 0

  const currencyOpts = balances.length > 0
    ? balances.map((b) => ({ value: b.currency, label: b.currency }))
    : [{ value: 'ARS', label: 'ARS' }]

  function handleClose() {
    setNewBalance('')
    setCurrency(defaultCurrency)
    setError('')
    onClose()
  }

  function handleSave() {
    const nuevo = parseAmount(newBalance)
    if (isNaN(nuevo)) { setError('Ingresá un número válido'); return }
    const diff = nuevo - currentBalance
    if (diff === 0) { handleClose(); return }
    create.mutate(
      {
        type: diff > 0 ? 'ingreso' : 'gasto',
        amount: Math.abs(diff),
        currency,
        account_id: account.id,
        description: 'Ajuste de saldo',
        kind: 'adjustment',
        occurred_at: new Date().toISOString().slice(0, 16),
      },
      { onSuccess: handleClose },
    )
  }

  return (
    <Modal open={open} onClose={handleClose} title="Ajustar saldo">
      <div style={{ display: 'grid', gap: 14 }}>
        {currencyOpts.length > 1 && (
          <label style={labelStyle}>
            Moneda
            <Select
              value={currency}
              onValueChange={(v) => { setCurrency(v as Currency); setNewBalance('') }}
              options={currencyOpts}
              ariaLabel="Moneda"
              style={{ width: '100%' }}
            />
          </label>
        )}

        <div style={{ fontSize: 13, color: 'var(--color-sage)' }}>
          Saldo actual:{' '}
          <span className="num-serif" style={{ fontSize: 16, color: 'var(--color-obsidian-ink)' }}>
            {formatMoney(currentBalance, currency)}
          </span>
        </div>

        <label style={labelStyle}>
          Nuevo saldo
          <input
            inputMode="decimal"
            value={newBalance}
            onChange={(e) => { setNewBalance(e.target.value); if (error) setError('') }}
            placeholder={String(currentBalance)}
            style={inputStyle}
          />
          {error && <span style={errorStyle}>{error}</span>}
          <span style={{ fontSize: 12, color: 'var(--color-sage)' }}>
            El ajuste no cuenta como gasto ni ingreso del mes.
          </span>
        </label>

        <div style={{ display: 'flex', gap: 8 }}>
          <button onClick={handleClose} style={ghostBtn}>Cancelar</button>
          <button onClick={handleSave} style={ctaBtn} disabled={create.isPending}>
            {create.isPending ? 'Guardando…' : 'Guardar'}
          </button>
        </div>
      </div>
    </Modal>
  )
}

const labelStyle: React.CSSProperties = { display: 'grid', gap: 4, fontSize: 13, color: 'var(--color-sage)' }
const errorStyle: React.CSSProperties = { fontSize: 12, color: 'var(--color-error)', marginTop: 2 }
const inputStyle: React.CSSProperties = {
  border: '1px solid var(--color-mist)',
  borderRadius: 10,
  padding: '10px 12px',
  fontSize: 14,
  background: 'var(--color-linen)',
  width: '100%',
  boxSizing: 'border-box',
}
const ghostBtn: React.CSSProperties = {
  flex: 1,
  background: 'transparent',
  border: '1px solid var(--color-mist)',
  borderRadius: 10,
  padding: '12px 14px',
  fontSize: 13,
  cursor: 'pointer',
}
const ctaBtn: React.CSSProperties = {
  flex: 2,
  background: 'var(--color-voltage)',
  color: 'var(--voltage-on-dark)',
  border: 'none',
  borderRadius: 10,
  padding: '12px 14px',
  fontWeight: 500,
  cursor: 'pointer',
}
