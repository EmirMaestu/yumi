import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { formatMoney } from './format'
import { type Currency } from './types'

// Ojito global para ocultar montos (UX16). Persistido en localStorage.
const KEY = 'yumi_hide_amounts'

interface PrivacyCtx { hidden: boolean; toggle: () => void }
const Ctx = createContext<PrivacyCtx>({ hidden: false, toggle: () => {} })

export function PrivacyProvider({ children }: { children: ReactNode }) {
  const [hidden, setHidden] = useState(() => {
    try { return localStorage.getItem(KEY) === '1' } catch { return false }
  })
  useEffect(() => {
    try { localStorage.setItem(KEY, hidden ? '1' : '0') } catch { /* ignore */ }
  }, [hidden])
  return <Ctx.Provider value={{ hidden, toggle: () => setHidden((h) => !h) }}>{children}</Ctx.Provider>
}

export function usePrivacy() { return useContext(Ctx) }

// Muestra el monto o "$ ••••" según el ojito. Reemplaza a formatMoney(...) en los
// héroes y KPIs. Fuera de esos lugares se sigue usando formatMoney directamente.
export function Money({ value, currency = 'ARS' }: { value: number; currency?: Currency }) {
  const { hidden } = usePrivacy()
  if (hidden) return <span aria-label="monto oculto">$ ••••</span>
  return <>{formatMoney(value, currency)}</>
}
