import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { PrivacyProvider, usePrivacy, Money } from './privacy'

function Harness() {
  const { toggle } = usePrivacy()
  return (
    <div>
      <button onClick={toggle}>toggle</button>
      <Money value={1500} />
    </div>
  )
}

describe('privacy / Money (UX16)', () => {
  it('muestra el monto formateado por defecto', () => {
    render(<PrivacyProvider><Money value={1500} /></PrivacyProvider>)
    expect(screen.getByText('$1.500,00')).toBeInTheDocument()
  })

  it('enmascara el monto al activar el ojito', async () => {
    const user = userEvent.setup()
    render(<PrivacyProvider><Harness /></PrivacyProvider>)
    expect(screen.getByText('$1.500,00')).toBeInTheDocument()
    await user.click(screen.getByText('toggle'))
    expect(screen.queryByText('$1.500,00')).toBeNull()
    expect(screen.getByText('$ ••••')).toBeInTheDocument()
  })
})
