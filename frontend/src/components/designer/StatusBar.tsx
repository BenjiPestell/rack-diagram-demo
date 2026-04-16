import css from './StatusBar.module.css'
import { useDesignerStore } from '../../store/designerStore'
import { expandRackDevices, expandDevices } from '../../utils/yaml'

export default function StatusBar() {
  const racks          = useDesignerStore(s => s.racks)
  const wiringLayers   = useDesignerStore(s => s.wiringLayers)
  const externalGroups = useDesignerStore(s => s.externalGroups)
  const saveStatus     = useDesignerStore(s => s.saveStatus)

  const deviceCount = racks.reduce((n, r) =>
    n + expandRackDevices(r.front).length + expandRackDevices(r.rear).length, 0)

  const extDevCount = externalGroups.reduce((n, g) =>
    n + expandDevices(g.devices).length, 0)

  const connCount = wiringLayers.reduce((n, l) => n + l.connections.length, 0)

  return (
    <div className={css.bar}>
      <span className={css.dot} />
      <span className={css.item}>{racks.length} rack{racks.length !== 1 ? 's' : ''}</span>
      <span className={css.sep}>·</span>
      <span className={css.item}>{deviceCount} devices</span>
      {extDevCount > 0 && <>
        <span className={css.sep}>·</span>
        <span className={css.item}>{extDevCount} external</span>
      </>}
      <span className={css.sep}>·</span>
      <span className={css.item}>{wiringLayers.length} layer{wiringLayers.length !== 1 ? 's' : ''}</span>
      <span className={css.sep}>·</span>
      <span className={css.item}>{connCount} connections</span>
      <div className={css.spacer} />
      {saveStatus === 'unsaved' && <span className={css.saveUnsaved}>● Unsaved</span>}
      {saveStatus === 'saving'  && <span className={css.saveSaving}>↑ Saving…</span>}
      {saveStatus === 'saved'   && <span className={css.saveSaved}>✓ Saved</span>}
      {saveStatus === 'error'   && <span className={css.saveError}>✕ Save failed</span>}
      {saveStatus !== 'idle' && <span className={css.sep}>·</span>}
      <span className={css.hint}>DEL — delete device</span>
      <span className={css.sep}>·</span>
      <span className={css.hint}>ESC — deselect / cancel pick</span>
    </div>
  )
}
