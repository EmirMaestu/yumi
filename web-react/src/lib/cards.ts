import { type Account, type Recurring } from './types'

export function arsBalance(acc: Pick<Account, 'balances'>): number {
  return (acc.balances ?? []).find(b => b.currency === 'ARS')?.balance ?? (acc.balances?.[0]?.balance ?? 0)
}

export function enCuotas(cardId: number, recurring: Recurring[] | undefined): number {
  return (recurring ?? []).filter(r => r.account_id === cardId && r.total_installments)
    .reduce((s, r) => s + r.amount * ((r.total_installments || 0) - (r.installments_fired || 0)), 0)
}

export function deudaTotal(cardId: number, acc: Pick<Account, 'balances'>, recurring: Recurring[] | undefined): number {
  return Math.abs(arsBalance(acc)) + enCuotas(cardId, recurring)
}
