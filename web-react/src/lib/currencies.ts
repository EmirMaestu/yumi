// Fuente única de las monedas soportadas (registrar/mostrar). El FX del backend hoy
// solo convierte USD↔ARS; el resto se guarda y muestra en su moneda (el patrimonio
// suma lo convertible y lista el resto aparte).
export const CURRENCY_CODES = ['ARS', 'USD', 'EUR', 'BRL', 'CLP', 'UYU', 'PYG', 'BOB'] as const
export type Currency = (typeof CURRENCY_CODES)[number]

// Símbolos distintos entre sí (ARS/CLP/UYU comparten "$" → los diferenciamos).
export const CURRENCY_SYMBOL: Record<Currency, string> = {
  ARS: '$', USD: 'US$', EUR: '€', BRL: 'R$', CLP: 'CLP$', UYU: '$U', PYG: '₲', BOB: 'Bs',
}

// Opciones para los <Select> de moneda (compacto: código + símbolo).
export const CURRENCY_OPTS = CURRENCY_CODES.map((c) => ({ value: c, label: `${c} ${CURRENCY_SYMBOL[c]}` }))
