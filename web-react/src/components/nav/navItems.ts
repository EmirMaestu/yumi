export interface NavItem { to: string; label: string; icon: string }

export const BOTTOM_NAV: NavItem[] = [
  { to: '/', label: 'Hoy', icon: 'ti-sparkles' },
  { to: '/finanzas', label: 'Finanzas', icon: 'ti-coin' },
  { to: '/agenda', label: 'Agenda', icon: 'ti-calendar' },
  { to: '/tareas', label: 'Tareas', icon: 'ti-checkbox' },
]

export interface NavGroup { title?: string; items: NavItem[] }

export const SIDEBAR_GROUPS: NavGroup[] = [
  {
    title: 'Asistente',
    items: [
      { to: '/', label: 'Hoy', icon: 'ti-sparkles' },
      { to: '/agenda', label: 'Agenda', icon: 'ti-calendar' },
      { to: '/tareas', label: 'Tareas', icon: 'ti-checkbox' },
      { to: '/listas', label: 'Listas', icon: 'ti-shopping-cart' },
      { to: '/habitos', label: 'Hábitos', icon: 'ti-flame' },
      { to: '/notas', label: 'Notas', icon: 'ti-note' },
    ],
  },
  {
    title: 'Finanzas',
    items: [
      { to: '/finanzas', label: 'Resumen', icon: 'ti-coin' },
      { to: '/movimientos', label: 'Movimientos', icon: 'ti-arrows-left-right' },
      { to: '/tarjetas', label: 'Tarjetas', icon: 'ti-credit-card' },
      { to: '/cuentas', label: 'Cuentas', icon: 'ti-wallet' },
      { to: '/categorias', label: 'Categorías', icon: 'ti-tags' },
      { to: '/recurrentes', label: 'Recurrentes', icon: 'ti-repeat' },
    ],
  },
  {
    items: [
      { to: '/perfil', label: 'Perfil', icon: 'ti-user' },
    ],
  },
]

export interface MenuLink { to: string; label: string; external?: boolean }
export interface MenuSection { title?: string; links: MenuLink[] }

export const MENU_LINKS: MenuSection[] = [
  {
    links: [
      { to: '/buscar', label: 'Búsqueda' },
      { to: '/listas', label: 'Listas' },
      { to: '/habitos', label: 'Hábitos' },
      { to: '/notas', label: 'Notas' },
    ],
  },
  {
    title: 'Finanzas',
    links: [
      { to: '/movimientos', label: 'Movimientos' },
      { to: '/tarjetas', label: 'Tarjetas' },
      { to: '/cuentas', label: 'Cuentas' },
      { to: '/categorias', label: 'Categorías' },
      { to: '/recurrentes', label: 'Recurrentes' },
    ],
  },
  {
    links: [
      { to: '/perfil', label: 'Perfil' },
    ],
  },
]
