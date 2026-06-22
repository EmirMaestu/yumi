import { formatMoney } from '../../lib/format'
import { type Currency } from '../../lib/types'
export default function MoneyText({ amount, currency = 'ARS', serif, size = 16 }:
  { amount: number; currency?: Currency; serif?: boolean; size?: number }) {
  return (
    <span className={serif ? 'num-serif' : undefined}
      style={{ fontSize: size, fontWeight: serif ? 300 : 500 }}>
      {formatMoney(amount, currency)}
    </span>
  )
}
