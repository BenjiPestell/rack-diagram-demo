import { useEffect } from 'react'
import { useDesignerStore } from '../../store/designerStore'
import css from './PickBanner.module.css'

const FIELD_LABELS: Record<string, string> = {
  from:            '"From" device',
  to:              '"To" device',
  via_patch_from:  '"Via Patch From" device',
  via_patch_to:    '"Via Patch To" device',
}

export default function PickBanner() {
  const pickState    = useDesignerStore(s => s.pickState)
  const exitPickMode = useDesignerStore(s => s.exitPickMode)

  // Escape key cancels pick mode
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') exitPickMode()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [exitPickMode])

  if (!pickState) return null

  const label = FIELD_LABELS[pickState.field] ?? pickState.field

  return (
    <div className={css.banner}>
      <span className={css.text}>
        Click a device in the canvas to set <strong>{label}</strong>
      </span>
      <button className={css.cancelBtn} onClick={exitPickMode}>
        Cancel (Esc)
      </button>
    </div>
  )
}
