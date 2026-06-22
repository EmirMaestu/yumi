export interface NavItem { to: string; label: string; icon: string }
export const NAV_ITEMS: NavItem[] = [
  { to: '/', label: 'Inicio', icon: 'ti-home' },
  { to: '/movimientos', label: 'Movim.', icon: 'ti-arrows-left-right' },
  { to: '/tarjetas', label: 'Tarjetas', icon: 'ti-credit-card' },
  { to: '/cuentas', label: 'Cuentas', icon: 'ti-wallet' },
]
