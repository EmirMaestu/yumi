import { forwardRef, type InputHTMLAttributes } from 'react'

const style: React.CSSProperties = {
  border: '1px solid var(--color-mist)', borderRadius: 10, padding: '10px 12px',
  fontSize: 14, background: 'var(--color-linen)', width: '100%', boxSizing: 'border-box',
}

// Input de texto con el estilo compartido. Passthrough de props (incluye register()).
const TextInput = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  function TextInput(props, ref) {
    return <input ref={ref} {...props} style={{ ...style, ...props.style }} />
  },
)
export default TextInput
