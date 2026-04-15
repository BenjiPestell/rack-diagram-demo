import { useState } from 'react'
import css from './Tabs.module.css'
import { useDesignerStore } from '../../../store/designerStore'

export default function ExternalTab() {
  const externalGroups      = useDesignerStore(s => s.externalGroups)
  const addExternalGroup    = useDesignerStore(s => s.addExternalGroup)
  const removeExternalGroup = useDesignerStore(s => s.removeExternalGroup)
  const updateGroupMeta     = useDesignerStore(s => s.updateGroupMeta)
  const addExternalDevice   = useDesignerStore(s => s.addExternalDevice)
  const removeExternalDevice = useDesignerStore(s => s.removeExternalDevice)
  const updateExternalDevice = useDesignerStore(s => s.updateExternalDevice)

  const [newDevNames, setNewDevNames] = useState<string[]>([])
  const [editingDev, setEditingDev]   = useState<{ gi: number; name: string } | null>(null)

  function handleNewDevName(groupIdx: number, val: string) {
    setNewDevNames(prev => {
      const next = [...prev]
      next[groupIdx] = val
      return next
    })
  }

  function addDevice(groupIdx: number) {
    const name = (newDevNames[groupIdx] ?? '').trim()
    if (!name) return
    addExternalDevice(groupIdx, { name })
    handleNewDevName(groupIdx, '')
  }

  return (
    <div className={css.tab}>
      {externalGroups.length === 0 && (
        <div className={css.empty}>No external device groups. Add one below.</div>
      )}

      {externalGroups.map((group, gi) => (
        <div key={gi} className={css.layer}>
          {/* Group header */}
          <div className={css.layerHeader}>
            <span className={css.layerName}>{group.name || `Group ${gi + 1}`}</span>
            <button
              className={css.iconBtn}
              onClick={() => removeExternalGroup(gi)}
              title="Remove group"
            >×</button>
          </div>

          <div className={css.layerBody}>
            <label className={css.field}>
              <span>Name</span>
              <input
                className={css.input}
                value={group.name}
                onChange={e => updateGroupMeta(gi, { name: e.target.value })}
              />
            </label>
            <label className={css.field}>
              <span>Distance (m)</span>
              <input
                className={css.input}
                type="number"
                step={0.5}
                value={group.distance_from_racks}
                onChange={e => updateGroupMeta(gi, { distance_from_racks: +e.target.value })}
              />
            </label>

            {/* Device list */}
            {group.devices.length > 0 && (
              <div className={css.deviceList}>
                {group.devices.map(dev => {
                  const isEditing = editingDev?.gi === gi && editingDev?.name === dev.name
                  return (
                    <div key={dev.name} className={css.extDevRow}>
                      {isEditing ? (
                        <div className={css.extDevEdit}>
                          <label className={css.connField}>
                            <span>Name</span>
                            <input
                              className={css.input}
                              defaultValue={dev.name}
                              onBlur={e => {
                                const newName = e.target.value.trim()
                                if (newName && newName !== dev.name) {
                                  updateExternalDevice(gi, dev.name, { name: newName })
                                  setEditingDev({ gi, name: newName })
                                }
                              }}
                            />
                          </label>
                          <label className={css.connField}>
                            <span>Type</span>
                            <input
                              className={css.input}
                              defaultValue={dev.type ?? ''}
                              placeholder="optional"
                              onBlur={e => updateExternalDevice(gi, dev.name, {
                                type: e.target.value.trim() || undefined,
                              })}
                            />
                          </label>
                          {dev.start != null && dev.end != null && (
                            <label className={css.connField}>
                              <span>Range</span>
                              <span className={css.dimText}>{dev.start}–{dev.end}</span>
                            </label>
                          )}
                          <button
                            className={css.addConnBtn}
                            style={{ marginTop: 4 }}
                            onClick={() => setEditingDev(null)}
                          >Done</button>
                        </div>
                      ) : (
                        <>
                          <span
                            style={{ cursor: 'pointer' }}
                            onClick={() => setEditingDev({ gi, name: dev.name })}
                          >
                            {dev.name}
                            {dev.type && <span className={css.dimText}> [{dev.type}]</span>}
                          </span>
                          {dev.start != null && dev.end != null && (
                            <span className={css.dimText}> ({dev.start}–{dev.end})</span>
                          )}
                          <button
                            className={css.iconBtn}
                            onClick={() => removeExternalDevice(gi, dev.name)}
                            title="Remove device"
                          >×</button>
                        </>
                      )}
                    </div>
                  )
                })}
              </div>
            )}

            {/* Add device */}
            <div className={css.addRow}>
              <input
                className={css.input}
                placeholder="Device name…"
                value={newDevNames[gi] ?? ''}
                onChange={e => handleNewDevName(gi, e.target.value)}
                onKeyDown={e => e.key === 'Enter' && addDevice(gi)}
              />
              <button className={css.addConnBtn} onClick={() => addDevice(gi)}>+</button>
            </div>
          </div>
        </div>
      ))}

      <button className={css.addLayerBtn} onClick={addExternalGroup}>
        + Add external group
      </button>
    </div>
  )
}
