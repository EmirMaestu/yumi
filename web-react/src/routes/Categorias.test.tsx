import { describe, it, expect } from 'vitest'
import { renderWithProviders } from '../test/utils'
import Categorias from './Categorias'

describe('Categorias', () => {
  it('muestra el skeleton mientras cargan las categorías (UX20)', () => {
    // Sin backend, la query queda en isLoading en el primer render → skeleton visible.
    const { container } = renderWithProviders(<Categorias />)
    expect(container.querySelector('.nf-skel')).not.toBeNull()
  })
})
