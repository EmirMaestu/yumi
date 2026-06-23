import { useMe, useSetScope } from '../../hooks/useMe'
import Select from '../ui/Select'

export default function ScopeToggle() {
  const { data: me } = useMe()
  const setScope = useSetScope()
  if (!me) return null
  const options = [
    { value: 'mine', label: 'Mío' },
    ...me.others.map((o) => ({ value: o.scope_value, label: o.name })),
    { value: 'both', label: 'Ambos' },
  ]
  return (
    <Select
      value={me.scope}
      onValueChange={(v) => setScope.mutate(v)}
      options={options}
      ariaLabel="Ver datos de"
      style={{ borderRadius: 9999, padding: '6px 11px', fontSize: 12 }}
    />
  )
}
