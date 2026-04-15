import { useState } from 'react'
import css from './Tabs.module.css'
import { useDesignerStore } from '../../../store/designerStore'

// ─── Pick button ──────────────────────────────────────────────────────────────

interface PickBtnProps {
  layerIdx: number
  connIdx: number
  field: string
  value: string
  placeholder?: string
}

function PickBtn({ layerIdx, connIdx, field, value, placeholder = '—pick—' }: PickBtnProps) {
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
      {isPicking ? '…' : value || placeholder}
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
  // Keys are "layerIdx:connIdx"
  const [expandedConns,  setExpandedConns]  = useState<Set<string>>(new Set())

  function toggleLayer(idx: number) {
    setExpandedLayers(prev => {
      const next = new Set(prev)
      next.has(idx) ? next.delete(idx) : next.add(idx)
      return next
    })
    setActiveLayer(idx)
  }

  function toggleConn(li: number, ci: number) {
    setExpandedConns(prev => {
      const next = new Set(prev)
      const key = `${li}:${ci}`
      next.has(key) ? next.delete(key) : next.add(key)
      return next
    })
  }

  function handleAddConnection(li: number) {
    const newIdx = wiringLayers[li].connections.length
    addConnection(li)
    // Auto-expand new empty connection
    setExpandedConns(prev => new Set([...prev, `${li}:${newIdx}`]))
  }

  return (
    <div className={css.tab}>
      {wiringLayers.length === 0 && (
        <div className={css.empty}>No wiring layers. Add one below.</div>
      )}

      {wiringLayers.map((layer, li) => {
        const layerExpanded = expandedLayers.has(li)
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
                {isViz ? 'Visualise ON' : 'Visualise'}
              </button>
              <button
                className={css.iconBtn}
                onClick={e => { e.stopPropagation(); removeWiringLayer(li) }}
                title="Remove layer"
              >×</button>
              <span className={css.chevron}>{layerExpanded ? '▲' : '▼'}</span>
            </div>

            {layerExpanded && (
              <div className={css.layerBody}>
                {/* Layer meta — 3 compact rows */}
                <div className={css.layerMeta}>
                  <label className={css.layerMetaRow}>
                    <span className={css.layerMetaKey}>Name</span>
                    <input
                      className={css.layerMetaInput}
                      value={layer.name}
                      onChange={e => updateLayerMeta(li, { name: e.target.value })}
                    />
                  </label>
                  <label className={css.layerMetaRow}>
                    <span className={css.layerMetaKey}>Color</span>
                    <input
                      type="color"
                      value={layer.edge_color ?? '#888888'}
                      onChange={e => updateLayerMeta(li, { edge_color: e.target.value })}
                    />
                  </label>
                  <label className={css.layerMetaRow}>
                    <span className={css.layerMetaKey}>Cable type</span>
                    <select
                      className={css.layerMetaSelect}
                      value={layer.cable_type ?? ''}
                      onChange={e => updateLayerMeta(li, { cable_type: e.target.value || undefined })}
                    >
                      <option value="">— none —</option>
                      {cableTypes.map(ct => <option key={ct} value={ct}>{ct}</option>)}
                    </select>
                  </label>
                </div>

                {/* Connections */}
                {layer.connections.length === 0 && (
                  <div className={css.connEmpty}>No connections in this layer.</div>
                )}

                {layer.connections.map((conn, ci) => {
                  const key        = `${li}:${ci}`
                  const isExpanded = expandedConns.has(key)
                  const toStr      = Array.isArray(conn.to)
                    ? conn.to.join(', ')
                    : (conn.to ?? '')
                  const hasPatch   = !!(conn.via_patch_from || conn.via_patch_to)
                  const hasExtras  = !!(conn.label || conn.edge_color || conn.cable_type)
                  const hasCluster = conn.start != null || conn.end != null
                  const hasPorts   = conn.from_port != null || conn.to_port != null
                  const hasIPs     = !!(conn.from_ip || conn.to_ip)

                  return (
                    <div key={ci} className={css.connRow}>

                      {/* ── Collapsed/expanded header ── */}
                      <div
                        className={css.connHeader}
                        onClick={() => toggleConn(li, ci)}
                      >
                        <span className={css.connIndexSmall}>#{ci + 1}</span>
                        <span className={css.connSummaryFrom} translate="no">
                          {conn.from || <em>from</em>}
                        </span>
                        <span className={css.connArrow}>→</span>
                        <span className={css.connSummaryTo} translate="no">
                          {toStr || <em>to</em>}
                        </span>
                        {/* Badge dots for non-empty optional sections */}
                        {!isExpanded && (hasPatch || hasExtras || hasCluster || hasPorts || hasIPs) && (
                          <span className={css.connBadges}>
                            {hasPatch   && <span className={css.badge} title="patch">P</span>}
                            {hasCluster && <span className={css.badge} title="cluster">N</span>}
                            {hasPorts   && <span className={css.badge} title="ports">#</span>}
                            {hasIPs     && <span className={css.badge} title="IPs">IP</span>}
                          </span>
                        )}
                        <button
                          className={css.iconBtn}
                          onClick={e => { e.stopPropagation(); removeConnection(li, ci) }}
                          title="Remove connection"
                        >×</button>
                        <span className={css.chevron}>{isExpanded ? '▲' : '▼'}</span>
                      </div>

                      {/* ── Expanded fields ── */}
                      {isExpanded && (
                        <div className={css.connFields}>

                          {/* ── Group 1: Devices ── */}
                          <div className={css.connGroup}>
                            <div className={css.pairRow}>
                              <div className={css.pairCell}>
                                <span className={css.pairLabel}>From</span>
                                <PickBtn layerIdx={li} connIdx={ci} field="from" value={conn.from} />
                              </div>
                              <div className={css.pairCell}>
                                <span className={css.pairLabel}>To</span>
                                <PickBtn layerIdx={li} connIdx={ci} field="to" value={toStr} />
                              </div>
                            </div>
                          </div>

                          {/* ── Group 2: Patch routing ── */}
                          <div className={css.connGroup}>
                            <div className={css.pairRow}>
                              <div className={css.pairCell}>
                                <span className={css.pairLabel}>Via patch (from)</span>
                                <PickBtn layerIdx={li} connIdx={ci} field="via_patch_from"
                                  value={conn.via_patch_from ?? ''} placeholder="— none —" />
                              </div>
                              <div className={css.pairCell}>
                                <span className={css.pairLabel}>Via patch (to)</span>
                                <PickBtn layerIdx={li} connIdx={ci} field="via_patch_to"
                                  value={conn.via_patch_to ?? ''} placeholder="— none —" />
                              </div>
                            </div>
                            {hasPatch && (
                              <div className={css.pairRow}>
                                <label className={css.pairCell}>
                                  <span className={css.pairLabel}>Patch port (from)</span>
                                  <input
                                    className={css.pairInput}
                                    type="number"
                                    value={conn.patch_port_from ?? ''}
                                    placeholder="auto"
                                    onChange={e => updateConnection(li, ci, {
                                      patch_port_from: e.target.value ? +e.target.value : undefined,
                                    })}
                                  />
                                </label>
                                <label className={css.pairCell}>
                                  <span className={css.pairLabel}>Patch port (to)</span>
                                  <input
                                    className={css.pairInput}
                                    type="number"
                                    value={conn.patch_port_to ?? ''}
                                    placeholder="auto"
                                    onChange={e => updateConnection(li, ci, {
                                      patch_port_to: e.target.value ? +e.target.value : undefined,
                                    })}
                                  />
                                </label>
                              </div>
                            )}
                          </div>

                          {/* ── Group 3: Ports & cluster range ── */}
                          <div className={css.connGroup}>
                            <div className={css.pairRow}>
                              <label className={css.pairCell}>
                                <span className={css.pairLabel}>From port</span>
                                <input
                                  className={css.pairInput}
                                  type="number"
                                  value={conn.from_port ?? ''}
                                  placeholder="auto"
                                  onChange={e => updateConnection(li, ci, {
                                    from_port: e.target.value ? +e.target.value : undefined,
                                  })}
                                />
                              </label>
                              <label className={css.pairCell}>
                                <span className={css.pairLabel}>To port</span>
                                <input
                                  className={css.pairInput}
                                  type="number"
                                  value={conn.to_port ?? ''}
                                  placeholder="auto"
                                  onChange={e => updateConnection(li, ci, {
                                    to_port: e.target.value ? +e.target.value : undefined,
                                  })}
                                />
                              </label>
                            </div>
                            <div className={css.pairRow}>
                              <label className={css.pairCell}>
                                <span className={css.pairLabel}>Cluster start N</span>
                                <input
                                  className={css.pairInput}
                                  type="number"
                                  value={conn.start ?? ''}
                                  placeholder="—"
                                  onChange={e => updateConnection(li, ci, {
                                    start: e.target.value ? +e.target.value : undefined,
                                  })}
                                />
                              </label>
                              <label className={css.pairCell}>
                                <span className={css.pairLabel}>Cluster end N</span>
                                <input
                                  className={css.pairInput}
                                  type="number"
                                  value={conn.end ?? ''}
                                  placeholder="—"
                                  onChange={e => updateConnection(li, ci, {
                                    end: e.target.value ? +e.target.value : undefined,
                                  })}
                                />
                              </label>
                            </div>
                          </div>

                          {/* ── Group 4: Addressing & label ── */}
                          <div className={css.connGroup}>
                            <div className={css.pairRow}>
                              <label className={css.pairCell}>
                                <span className={css.pairLabel}>From IP</span>
                                <input
                                  className={css.pairInputText}
                                  value={conn.from_ip ?? ''}
                                  placeholder="optional"
                                  onChange={e => updateConnection(li, ci, {
                                    from_ip: e.target.value || undefined,
                                  })}
                                />
                              </label>
                              <label className={css.pairCell}>
                                <span className={css.pairLabel}>To IP</span>
                                <input
                                  className={css.pairInputText}
                                  value={conn.to_ip ?? ''}
                                  placeholder="optional"
                                  onChange={e => updateConnection(li, ci, {
                                    to_ip: e.target.value || undefined,
                                  })}
                                />
                              </label>
                            </div>
                            <label className={css.pairCell}>
                              <span className={css.pairLabel}>Label</span>
                              <input
                                className={css.connLabelInput}
                                value={conn.label ?? ''}
                                placeholder="optional"
                                onChange={e => updateConnection(li, ci, {
                                  label: e.target.value || undefined,
                                })}
                              />
                            </label>
                          </div>

                          {/* ── Group 5: Style ── */}
                          <div className={css.connGroup}>
                            <div className={css.pairRow} style={{ alignItems: 'flex-end' }}>
                              <label className={css.pairCell}>
                                <span className={css.pairLabel}>Cable type</span>
                                <select
                                  className={css.pairSelect}
                                  value={conn.cable_type ?? ''}
                                  onChange={e => updateConnection(li, ci, {
                                    cable_type: e.target.value || undefined,
                                  })}
                                >
                                  <option value="">— inherit —</option>
                                  {cableTypes.map(ct => <option key={ct} value={ct}>{ct}</option>)}
                                </select>
                              </label>
                              <label className={css.pairCell}>
                                <span className={css.pairLabel}>Color override</span>
                                <div className={css.colorRow}>
                                  <input
                                    type="color"
                                    value={conn.edge_color ?? layer.edge_color ?? '#888888'}
                                    onChange={e => updateConnection(li, ci, {
                                      edge_color: e.target.value,
                                    })}
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
                            </div>
                          </div>

                        </div>
                      )}
                    </div>
                  )
                })}

                <button
                  className={css.addConnBtn}
                  onClick={() => handleAddConnection(li)}
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
