import { screen } from '@testing-library/react'
import { renderWithProviders } from '../../test/utils'
import CategoryBar from './CategoryBar'

test('renderiza label y total formateado', () => {
  renderWithProviders(<CategoryBar label="Comida" total={210000} max={210000} />)
  expect(screen.getByText('Comida')).toBeInTheDocument()
  expect(screen.getByText('$210.000')).toBeInTheDocument()
})
