// Paleta fija de 12 colores para categorías/series (D11). Elegidos con contraste
// razonable sobre fondo claro y oscuro.
export const PALETTE = [
  '#2563eb', '#dc2626', '#16a34a', '#d97706',
  '#7c3aed', '#0891b2', '#db2777', '#65a30d',
  '#ea580c', '#4f46e5', '#0d9488', '#9333ea',
]

export function paletteColor(i: number): string {
  return PALETTE[i % PALETTE.length]
}
