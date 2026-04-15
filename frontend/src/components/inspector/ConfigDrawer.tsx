import css from './ConfigDrawer.module.css'
import type { CableConfig } from '../../types'

interface Props {
  config: CableConfig
  onChange: (cfg: CableConfig) => void
}

const fields: { key: keyof CableConfig; label: string; step: number }[] = [
  { key: 'interRack',   label: 'Inter-rack dist (m)', step: 0.5 },
  { key: 'frontToBack', label: 'Front-to-back (m)',   step: 0.1 },
  { key: 'slack',       label: 'Max slack (m)',        step: 0.1 },
  { key: 'uHeight',     label: 'U height (m)',         step: 0.001 },
  { key: 'railExt',     label: 'Rail extension (m)',   step: 0.1 },
]

export default function ConfigDrawer({ config, onChange }: Props) {
  function set(key: keyof CableConfig, val: string) {
    const n = parseFloat(val)
    if (!isNaN(n)) onChange({ ...config, [key]: n })
  }

  return (
    <div className={css.drawer}>
      {fields.map(f => (
        <div key={f.key} className={css.field}>
          <label className={css.label}>{f.label}</label>
          <input
            className={css.input}
            type="number"
            step={f.step}
            value={config[f.key]}
            onChange={e => set(f.key, e.target.value)}
          />
        </div>
      ))}
    </div>
  )
}
