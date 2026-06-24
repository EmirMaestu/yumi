import { type Account, type Recurring, type CicloTotal, type VencimientoCard } from './types'

// ── Única fuente de verdad para los montos de una tarjeta ──────────────────
// Convenciones (acordadas con el usuario):
//  • Consumos        = |saldo ARS| (transacciones de la tarjeta)
//  • Cuotas por venir = Σ monto × (total − pagadas), incluye PAUSADAS (siguen siendo deuda)
//  • Deuda total     = consumos + cuotas por venir
//  • A pagar ahora   = ciclo cerrado (el resumen que vence), NO la deuda total
//  • Cuota actual    = pagadas + 1 (igual que el bot)

export function arsBalance(acc: Pick<Account, 'balances'>): number {
  return (acc.balances ?? []).find(b => b.currency === 'ARS')?.balance ?? (acc.balances?.[0]?.balance ?? 0)
}

export function consumos(acc: Pick<Account, 'balances'>): number {
  return Math.abs(arsBalance(acc))
}

// Cuotas que todavía van a caer. Incluye planes pausados (active=0): pausar no
// borra la deuda. Excluye los terminados (restante 0 no suma).
export function enCuotas(cardId: number, recurring: Recurring[] | undefined): number {
  return (recurring ?? []).filter(r => r.account_id === cardId && r.total_installments)
    .reduce((s, r) => s + r.amount * Math.max(0, (r.total_installments || 0) - (r.installments_fired || 0)), 0)
}

export function deudaTotal(cardId: number, acc: Pick<Account, 'balances'>, recurring: Recurring[] | undefined): number {
  return consumos(acc) + enCuotas(cardId, recurring)
}

// Nº de cuota que se está pagando ahora (pagadas + 1), tope en el total.
export function cuotaActual(r: Pick<Recurring, 'installments_fired' | 'total_installments'>): number {
  const total = r.total_installments ?? 0
  if (!total) return 0
  return Math.min((r.installments_fired ?? 0) + 1, total)
}

// Suma en ARS de un ciclo (cerrado o abierto) de una tarjeta.
export function cicloArs(arr: CicloTotal[] | undefined): number {
  return (arr ?? []).filter(c => c.currency === 'ARS').reduce((s, c) => s + c.total, 0)
}

// "A pagar ahora" de una tarjeta = total del ciclo cerrado (lo que vence).
export function aPagarCard(venc: VencimientoCard | undefined): number {
  return cicloArs(venc?.ciclo_cerrado)
}

// "A pagar ahora" sumado de todas las tarjetas (para el Home).
export function aPagarTotal(venc: VencimientoCard[] | undefined): number {
  return (venc ?? []).reduce((s, v) => s + cicloArs(v.ciclo_cerrado), 0)
}
