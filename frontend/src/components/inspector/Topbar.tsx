import css from './Topbar.module.css'

interface Props {
  connected: boolean
  onReload: () => void
  onToggleConfig: () => void
}

export default function Topbar({ connected, onReload, onToggleConfig }: Props) {
  return (
    <div className={css.bar}>
      <div className={css.logo}>RACK <span>INSPECTOR</span></div>
      <div className={css.spacer} />
      <div className={css.dot} style={{ background: connected ? '#3fb950' : '#f85149' }} />
      <button className={css.iconBtn} title="Settings" onClick={onToggleConfig}>⚙</button>
      <button className={css.iconBtn} title="Reload" onClick={onReload}>↺</button>
    </div>
  )
}
