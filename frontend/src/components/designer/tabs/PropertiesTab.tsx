import css from './Tabs.module.css'
import { useDesignerStore } from '../../../store/designerStore'

export default function PropertiesTab() {
  const selectedDevRef = useDesignerStore(s => s.selectedDevRef)
  const typeList       = useDesignerStore(s => s.typeEntries)
  const updateDevice   = useDesignerStore(s => s.updateDevice)
  const removeDevice   = useDesignerStore(s => s.removeDevice)
  const selectDevice   = useDesignerStore(s => s.selectDevice)
  const openPortAssign = useDesignerStore(s => s.openPortAssign)

  if (!selectedDevRef) {
    return (
      <div className={css.empty}>
        Select a device in the canvas to edit its properties.
      </div>
    )
  }

  const { dev, rackId, face } = selectedDevRef
  const isCluster = dev.name.includes('{N}') && dev.start != null && dev.end != null

  // Determine if the type is "ported" (i.e. has a ports count or type.ported)
  const typeEntry = typeList.find(e => e.type === dev.type)
  const hasPorts  = dev.ports != null || typeEntry?.ported

  function update(changes: Parameters<typeof updateDevice>[3]) {
    updateDevice(rackId, face, dev.name, changes)
  }

  function handleDelete() {
    removeDevice(rackId, face, dev.name)
    selectDevice(null)
  }

  return (
    <div className={css.tab}>
      <div className={css.section}>
        <div className={css.sectionTitle}>Identity</div>

        <label className={css.field}>
          <span>Name</span>
          <input
            className={css.input}
            value={dev.name}
            onChange={e => update({ name: e.target.value })}
          />
        </label>

        <label className={css.field}>
          <span>Type</span>
          <select
            className={css.select}
            value={dev.type ?? ''}
            onChange={e => update({ type: e.target.value || undefined })}
          >
            <option value="">— none —</option>
            {typeList.map(e => (
              <option key={e.type} value={e.type}>{e.type}</option>
            ))}
          </select>
        </label>
      </div>

      <div className={css.section}>
        <div className={css.sectionTitle}>Position</div>

        <label className={css.field}>
          <span>Start U</span>
          <input
            className={css.input}
            type="number"
            value={dev.start_u ?? ''}
            placeholder="unpositioned"
            onChange={e => update({ start_u: e.target.value ? +e.target.value : undefined })}
          />
        </label>

        <label className={css.field}>
          <span>Units</span>
          <input
            className={css.input}
            type="number"
            min={1}
            value={dev.units ?? 1}
            onChange={e => update({ units: +e.target.value })}
          />
        </label>

        <label className={css.field}>
          <span>Cable exit</span>
          <select
            className={css.select}
            value={dev.cable_exit ?? 'rear'}
            onChange={e => update({ cable_exit: e.target.value as 'front' | 'rear' })}
          >
            <option value="rear">Rear</option>
            <option value="front">Front</option>
          </select>
        </label>

        <label className={`${css.field} ${css.checkField}`}>
          <input
            type="checkbox"
            checked={dev.on_rails ?? false}
            onChange={e => update({ on_rails: e.target.checked || undefined })}
          />
          <span>On rails</span>
        </label>
      </div>

      {isCluster && (
        <div className={css.section}>
          <div className={css.sectionTitle}>Cluster</div>

          <label className={css.field}>
            <span>Start N</span>
            <input
              className={css.input}
              type="number"
              value={dev.start ?? ''}
              onChange={e => update({ start: e.target.value ? +e.target.value : undefined })}
            />
          </label>

          <label className={css.field}>
            <span>End N</span>
            <input
              className={css.input}
              type="number"
              value={dev.end ?? ''}
              onChange={e => update({ end: e.target.value ? +e.target.value : undefined })}
            />
          </label>

          <label className={css.field}>
            <span>Spacing (U)</span>
            <input
              className={css.input}
              type="number"
              min={0}
              value={dev.spacing ?? 0}
              onChange={e => update({ spacing: +e.target.value || undefined })}
            />
          </label>
        </div>
      )}

      <div className={css.section}>
        <div className={css.sectionTitle}>Ports</div>
        <label className={css.field}>
          <span>Port count</span>
          <input
            className={css.input}
            type="number"
            min={0}
            value={dev.ports ?? ''}
            placeholder="none"
            onChange={e => update({ ports: e.target.value ? +e.target.value : undefined })}
          />
        </label>
        {hasPorts && (
          <div className={css.field}>
            <span></span>
            <button
              className={css.assignPortsBtn}
              onClick={() => openPortAssign(selectedDevRef.displayName)}
            >
              Assign ports
            </button>
          </div>
        )}
      </div>

      <div className={css.section}>
        <div className={css.sectionTitle}>Location</div>
        <div className={css.metaRow}>
          <span className={css.metaKey}>Rack</span>
          <span className={css.metaVal}>{rackId}</span>
        </div>
        <div className={css.metaRow}>
          <span className={css.metaKey}>Face</span>
          <span className={css.metaVal}>{face}</span>
        </div>
      </div>

      <div className={css.footer}>
        <button className={css.deleteBtn} onClick={handleDelete}>Delete device</button>
      </div>
    </div>
  )
}
