import { useState } from 'react'
import css from './Tabs.module.css'
import { useDesignerStore } from '../../../store/designerStore'

// ─── Pick button ──────────────────────────────────────────────────────────────

interface PickBtnProps {
  layerIdx: number
  connIdx: number
  field: string
  value: string
}

function PickBtn({ layerIdx, connIdx, field, value }: PickBtnProps) {
  const pickState     = useDesignerStore(s => s.pickState)
  const enterPickMode = useDesignerStore(s => s.enterPickMode)
  const isPicking =
    pickState?.layerIdx === layerIdx &&
    pickState?.connIdx === connIdx &&
    pickState?.field === field

  return (
    <button
      className={isPicking ? css.pickBtnActive : css.pickBtn}
      onClick={() => enterPickMode(layerIdx, connIdx, field)}
      title={isPicking ? 'Waiting for click…' : 'Pick from canvas'}
    >
      {isPicking ? '…' : value || '—pick—'}
    </button>
  )
}

// ─── WiringTab ────────────────────────────────────────────────────────────────

export default function WiringTab() {
  const wiringLayers      = useDesignerStore(s => s.wiringLayers)
  const cableTypes        = useDesignerStore(s => s.cableTypes)
  const activeLayerIdx    = useDesignerStore(s => s.activeLayerIdx)
  const vizLayerIdx       = useDesignerStore(s => s.vizLayerIdx)
  const addWiringLayer    = useDesignerStore(s => s.addWiringLayer)
  const removeWiringLayer = useDesignerStore(s => s.removeWiringLayer)
  const updateLayerMeta   = useDesignerStore(s => s.updateLayerMeta)
  const addConnection     = useDesignerStore(s => s.addConnection)
  const removeConnection  = useDesignerStore(s => s.removeConnection)
  const updateConnection  = useDesignerStore(s => s.updateConnection)
  const setActiveLayer    = useDesignerStore(s => s.setActiveLayer)
  const setVizLayer       = useDesignerStore(s => s.setVizLayer)

  const [expandedLayers, setExpandedLayers] = useState<Set<number>>(new Set([0]))

  function toggleLayer(idx: number) {
    setExpandedLayers(prev => {
      const next = new Set(prev)
      next.has(idx) ? next.delete(idx) : next.add(idx)
      return next
    })
    setActiveLayer(idx)
  }

  return (
    <div className={css.tab}>
      {wiringLayers.length === 0 && (
        <div className={css.empty}>No wiring layers. Add one below.</div>
      )}

      {wiringLayers.map((layer, li) => {
        const expanded = expandedLayers.has(li)
        const isActive = activeLayerIdx === li
        const isViz    = vizLayerIdx === li
        return (
          <div key={li} className={`${css.layer} ${isActive ? css.layerActive : ''}`}>
            {/* Layer header */}
            <div className={css.layerHeader} onClick={() => toggleLayer(li)}>
              <span
                className={css.layerDot}
                style={{ background: layer.edge_color ?? '#888' }}
              />
              <span className={css.layerName}>{layer.name || `Layer ${li + 1}`}</span>
              <span className={css.layerCount}>{layer.connections.length} conn</span>
              <button
                className={isViz ? css.vizBtnOn : css.vizBtn}
                onClick={e => { e.stopPropagation(); setVizLayer(li) }}
                title={isViz ? 'Hide wiring' : 'Visualise on canvas'}
              >
                {isViz ? 'VIZ ON' : 'VIZ'}
              </button>
              <button
                className={css.iconBtn}
                onClick={e => { e.stopPropagation(); removeWiringLayer(li) }}
                title="Remove layer"
              >×</button>
              <span className={css.chevron}>{expanded ? '▲' : '▼'}</span>
            </div>

            {expanded && (
              <div className={css.layerBody}>
                {/* Layer meta */}
                <label className={css.field}>
                  <span>Name</span>
                  <input
                    className={css.input}
                    value={layer.name}
                    onChange={e => updateLayerMeta(li, { name: e.target.value })}
                  />
                </label>
                <label className={css.field}>
                  <span>Color</span>
                  <input
                    type="color"
                    value={layer.edge_color ?? '#888888'}
                    onChange={e => updateLayerMeta(li, { edge_color: e.target.value })}
                  />
                </label>
                <label className={css.field}>
                  <span>Cable type</span>
                  <select
                    className={css.select}
                    value={layer.cable_type ?? ''}
                    onChange={e => updateLayerMeta(li, { cable_type: e.target.value || undefined })}
                  >
                    <option value="">— none —</option>
                    {cableTypes.map(ct => <option key={ct} value={ct}>{ct}</option>)}
                  </select>
                </label>

                {/* Connections */}
                {layer.connections.length === 0 && (
                  <div className={css.connEmpty}>No connections in this layer.</div>
                )}
                {layer.connections.map((conn, ci) => (
                  <div key={ci} className={css.connRow}>
                    <div className={css.connIndex}>#{ci + 1}</div>

                    <div className={css.connFields}>
                      <label className={css.connField}>
                        <span>From</span>
                        <PickBtn layerIdx={li} connIdx={ci} field="from" value={conn.from} />
                      </label>
                      <label className={css.connField}>
                        <span>To</span>
                        <PickBtn layerIdx={li} connIdx={ci} field="to" value={conn.to} />
                      </label>
                      <label className={css.connField}>
                        <span>Via patch (from)</span>
                        <PickBtn layerIdx={li} connIdx={ci} field="via_patch_from" value={conn.via_patch_from ?? ''} />
                      </label>
                      <label className={css.connField}>
                        <span>Via patch (to)</span>
                        <PickBtn layerIdx={li} connIdx={ci} field="via_patch_to" value={conn.via_patch_to ?? ''} />
                      </label>
                      {conn.via_patch_from && (
                        <label className={css.connField}>
                          <span>Patch port (from)</span>
                          <input
                            className={css.input}
                            type="number"
                            value={conn.patch_port_from ?? ''}
                            placeholder="auto"
                            onChange={e => updateConnection(li, ci, {
                              patch_port_from: e.target.value ? +e.target.value : undefined,
                            })}
                          />
                        </label>
                      )}
                      {conn.via_patch_to && (
                        <label className={css.connField}>
                          <span>Patch port (to)</span>
                          <input
                            className={css.input}
                            type="number"
                            value={conn.patch_port_to ?? ''}
                            placeholder="auto"
                            onChange={e => updateConnection(li, ci, {
                              patch_port_to: e.target.value ? +e.target.value : undefined,
                            })}
                          />
                        </label>
                      )}

                      {/* Label */}
                      <label className={css.connField}>
                        <span>Label</span>
                        <input
                          className={css.input}
                          value={conn.label ?? ''}
                          placeholder="optional"
                          onChange={e => updateConnection(li, ci, { label: e.target.value || undefined })}
                        />
                      </label>

                      {/* Color override */}
                      <label className={css.connField}>
                        <span>Color override</span>
                        <div className={css.colorRow}>
                          <input
                            type="color"
                            value={conn.edge_color ?? layer.edge_color ?? '#888888'}
                            onChange={e => updateConnection(li, ci, { edge_color: e.target.value })}
                          />
                          {conn.edge_color && (
                            <button
                              className={css.clearColorBtn}
                              onClick={() => updateConnection(li, ci, { edge_color: undefined })}
                              title="Reset to layer color"
                            >↺</button>
                          )}
                        </div>
                      </label>

                      {/* Cable type override */}
                      <label className={css.connField}>
                        <span>Cable type</span>
                        <select
                          className={css.select}
                          value={conn.cable_type ?? ''}
                          onChange={e => updateConnection(li, ci, { cable_type: e.target.value || undefined })}
                        >
                          <option value="">— inherit —</option>
                          {cableTypes.map(ct => <option key={ct} value={ct}>{ct}</option>)}
                        </select>
                      </label>

                      {/* Cluster range */}
                      <label className={css.connField}>
                        <span>Cluster start N</span>
                        <input
                          className={css.input}
                          type="number"
                          value={conn.start ?? ''}
                          placeholder="auto"
                          onChange={e => updateConnection(li, ci, { start: e.target.value ? +e.target.value : undefined })}
                        />
                      </label>
                      <label className={css.connField}>
                        <span>Cluster end N</span>
                        <input
                          className={css.input}
                          type="number"
                          value={conn.end ?? ''}
                          placeholder="auto"
                          onChange={e => updateConnection(li, ci, { end: e.target.value ? +e.target.value : undefined })}
                        />
                      </label>

                      {/* Port specs */}
                      <label className={css.connField}>
                        <span>From port</span>
                        <input
                          className={css.input}
                          type="number"
                          value={conn.from_port ?? ''}
                          placeholder="auto"
                          onChange={e => updateConnection(li, ci, { from_port: e.target.value ? +e.target.value : undefined })}
                        />
                      </label>
                      <label className={css.connField}>
                        <span>To port</span>
                        <input
                          className={css.input}
                          type="number"
                          value={conn.to_port ?? ''}
                          placeholder="auto"
                          onChange={e => updateConnection(li, ci, { to_port: e.target.value ? +e.target.value : undefined })}
                        />
                      </label>

                      {/* IP addresses */}
                      <label className={css.connField}>
                        <span>From IP</span>
                        <input
                          className={css.input}
                          value={conn.from_ip ?? ''}
                          placeholder="optional"
                          onChange={e => updateConnection(li, ci, { from_ip: e.target.value || undefined })}
                        />
                      </label>
                      <label className={css.connField}>
                        <span>To IP</span>
                        <input
                          className={css.input}
                          value={conn.to_ip ?? ''}
                          placeholder="optional"
                          onChange={e => updateConnection(li, ci, { to_ip: e.target.value || undefined })}
                        />
                      </label>
                    </div>

                    <button
                      className={css.iconBtn}
                      style={{ alignSelf: 'flex-start', marginTop: 2 }}
                      onClick={() => removeConnection(li, ci)}
                      title="Remove connection"
                    >×</button>
                  </div>
                ))}

                <button
                  className={css.addConnBtn}
                  onClick={() => addConnection(li)}
                >
                  + Add connection
                </button>
              </div>
            )}
          </div>
        )
      })}

      <button className={css.addLayerBtn} onClick={addWiringLayer}>
        + Add wiring layer
      </button>
    </div>
  )
}
