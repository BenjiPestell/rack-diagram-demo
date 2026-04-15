import { useState } from 'react'
import { useDesignerStore } from '../../store/designerStore'
import css from './LeftPanel.module.css'

export default function LeftPanel() {
  const typeEntries         = useDesignerStore(s => s.typeEntries)
  const cableTypes          = useDesignerStore(s => s.cableTypes)
  const interRackDistance   = useDesignerStore(s => s.interRackDistance)
  const cableSlackLength    = useDesignerStore(s => s.cableSlackLength)
  const frontToBackLength   = useDesignerStore(s => s.frontToBackLength)
  const railExtensionLength = useDesignerStore(s => s.railExtensionLength)
  const standardUHeight     = useDesignerStore(s => s.standardUHeight)
  const addRack             = useDesignerStore(s => s.addRack)
  const addTypeEntry        = useDesignerStore(s => s.addTypeEntry)
  const removeTypeEntry     = useDesignerStore(s => s.removeTypeEntry)
  const updateTypeEntry     = useDesignerStore(s => s.updateTypeEntry)
  const addCableType        = useDesignerStore(s => s.addCableType)
  const removeCableType     = useDesignerStore(s => s.removeCableType)
  const setCableConfig      = useDesignerStore(s => s.setCableConfig)

  const [newTypeName,  setNewTypeName]  = useState('')
  const [newTypeColor, setNewTypeColor] = useState('#3a7bd5')
  const [newCableType, setNewCableType] = useState('')
  const [showConfig,   setShowConfig]   = useState(false)
  const [showCables,   setShowCables]   = useState(false)

  function addType() {
    const t = newTypeName.trim()
    if (!t) return
    addTypeEntry({ type: t, color: newTypeColor, units: 1 })
    setNewTypeName('')
  }

  function addCable() {
    const c = newCableType.trim()
    if (!c) return
    addCableType(c)
    setNewCableType('')
  }

  return (
    <div className={css.panel}>
      <button className={css.addRackBtn} onClick={addRack}>+ Add Rack</button>

      <div className={css.sectionHeader}>Device Types</div>
      <div className={css.typeList}>
        {typeEntries.map(e => (
          <div
            key={e.type}
            className={css.typeRow}
            draggable
            onDragStart={ev => {
              ev.dataTransfer.setData('rack-designer/payload',
                JSON.stringify({ kind: 'palette', typeName: e.type }))
              ev.dataTransfer.effectAllowed = 'copy'
            }}
            title={`Drag to place ${e.type}`}
          >
            <span className={css.typeDot} style={{ background: e.color }} />
            <span className={css.typeName}>{e.type}</span>
            <input
              type="color"
              className={css.colorInput}
              value={e.color}
              title="Change color"
              onChange={ev => updateTypeEntry(e.type, { color: ev.target.value })}
            />
            <button
              className={css.iconBtn}
              title="Remove type"
              onClick={() => removeTypeEntry(e.type)}
            >×</button>
          </div>
        ))}
      </div>
      <div className={css.addRow}>
        <input
          className={css.textInput}
          placeholder="New type…"
          value={newTypeName}
          onChange={e => setNewTypeName(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && addType()}
        />
        <input
          type="color"
          className={css.colorInput}
          value={newTypeColor}
          onChange={e => setNewTypeColor(e.target.value)}
        />
        <button className={css.addBtn} onClick={addType} title="Add type">+</button>
      </div>

      {/* Cable config */}
      <div className={css.collapsible}>
        <button
          className={css.collapsibleHeader}
          onClick={() => setShowConfig(v => !v)}
        >
          <span>Cable Config</span>
          <span>{showConfig ? '▲' : '▼'}</span>
        </button>
        {showConfig && (
          <div className={css.configGrid}>
            <label>
              Inter-rack (m)
              <input type="number" step={0.1} value={interRackDistance}
                onChange={e => setCableConfig({ interRackDistance: +e.target.value })} />
            </label>
            <label>
              Slack (m)
              <input type="number" step={0.05} value={cableSlackLength}
                onChange={e => setCableConfig({ cableSlackLength: +e.target.value })} />
            </label>
            <label>
              Front-to-back (m)
              <input type="number" step={0.05} value={frontToBackLength}
                onChange={e => setCableConfig({ frontToBackLength: +e.target.value })} />
            </label>
            <label>
              Rail ext (m)
              <input type="number" step={0.05} value={railExtensionLength}
                onChange={e => setCableConfig({ railExtensionLength: +e.target.value })} />
            </label>
            <label>
              U height (m)
              <input type="number" step={0.001} value={standardUHeight}
                onChange={e => setCableConfig({ standardUHeight: +e.target.value })} />
            </label>
          </div>
        )}
      </div>

      {/* Cable types */}
      <div className={css.collapsible}>
        <button
          className={css.collapsibleHeader}
          onClick={() => setShowCables(v => !v)}
        >
          <span>Cable Types</span>
          <span>{showCables ? '▲' : '▼'}</span>
        </button>
        {showCables && (
          <>
            {cableTypes.map(ct => (
              <div key={ct} className={css.cableItem}>
                <span>{ct}</span>
                <button className={css.iconBtn} onClick={() => removeCableType(ct)}>×</button>
              </div>
            ))}
            <div className={css.addRow}>
              <input
                className={css.textInput}
                placeholder="Cable type…"
                value={newCableType}
                onChange={e => setNewCableType(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && addCable()}
              />
              <button className={css.addBtn} onClick={addCable}>+</button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
