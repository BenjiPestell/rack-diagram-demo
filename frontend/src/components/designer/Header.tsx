import { useDesignerStore } from '../../store/designerStore'
import css from './Header.module.css'

export default function Header() {
  const startRun       = useDesignerStore(s => s.startRun)
  const isRunning      = useDesignerStore(s => s.isRunning)
  const showRunPanel   = useDesignerStore(s => s.showRunPanel)
  const toggleRunPanel = useDesignerStore(s => s.toggleRunPanel)
  const loadSampleData = useDesignerStore(s => s.loadSampleData)
  const clearAll       = useDesignerStore(s => s.clearAll)
  const loadFromYaml   = useDesignerStore(s => s.loadFromYaml)

  async function handleLoad() {
    try {
      const r = await fetch('/yaml')
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      loadFromYaml(await r.text())
    } catch (e) {
      alert(`Load failed: ${e}`)
    }
  }

  function handleClearAll() {
    if (window.confirm('Clear all racks, wiring and external groups?')) {
      clearAll()
    }
  }

  return (
    <div className={css.bar}>
      <div className={css.logo}>RACK <span>DESIGNER</span></div>
      <div className={css.spacer} />
      <button className={css.btn} onClick={loadSampleData} title="Load example configuration">
        Load example
      </button>
      <button className={css.btn} onClick={handleLoad}>From server</button>
      <button className={css.btn} onClick={handleClearAll} title="Clear entire workspace">
        Clear all
      </button>
      {showRunPanel && (
        <button className={css.btn} onClick={toggleRunPanel} title="Toggle output panel">
          {showRunPanel ? 'Hide output' : 'Show output'}
        </button>
      )}
      <button
        className={css.btnPrimary}
        onClick={startRun}
        disabled={isRunning}
      >
        {isRunning ? 'Running…' : 'Save & Run'}
      </button>
    </div>
  )
}
