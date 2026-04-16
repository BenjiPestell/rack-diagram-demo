import { useMemo, useRef, useState } from 'react'
import css from './Tabs.module.css'
import { useDesignerStore } from '../../../store/designerStore'

export default function YAMLTab() {
  const generateYaml = useDesignerStore(s => s.generateYaml)
  const loadFromYaml = useDesignerStore(s => s.loadFromYaml)
  // version increments on every store mutation — drives live YAML recompute
  const version      = useDesignerStore(s => s.version)

  // Live YAML — always reflects current store state
  const liveYaml = useMemo(() => generateYaml(), [version]) // eslint-disable-line react-hooks/exhaustive-deps

  const [editMode, setEditMode] = useState(false)
  const [editText, setEditText] = useState('')
  const [error,    setError]    = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // ── Edit mode helpers ───────────────────────────────────────────────────

  function enterEdit() {
    setEditText(liveYaml)
    setEditMode(true)
    setError(null)
  }

  function applyEdit() {
    try {
      loadFromYaml(editText)
      setEditMode(false)
      setError(null)
    } catch (e) {
      setError(String(e))
    }
  }

  function discardEdit() {
    setEditMode(false)
    setError(null)
  }

  // ── Shared helpers ──────────────────────────────────────────────────────

  function copyToClipboard() {
    navigator.clipboard.writeText(editMode ? editText : liveYaml).catch(() => {})
  }

  function downloadFile() {
    const blob = new Blob([editMode ? editText : liveYaml], { type: 'text/yaml' })
    const url  = URL.createObjectURL(blob)
    const a    = document.createElement('a')
    a.href     = url
    a.download = 'system.yaml'
    a.click()
    URL.revokeObjectURL(url)
  }

  function openFilePicker() {
    fileInputRef.current?.click()
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = ev => {
      const text = ev.target?.result as string
      if (editMode) {
        // In edit mode: load into the editor
        setEditText(text)
      } else {
        // In live mode: apply immediately to state
        loadFromYaml(text)
      }
      setError(null)
    }
    reader.readAsText(file)
    e.target.value = ''
  }

  async function loadFromServer() {
    try {
      const r = await fetch('/yaml')
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      const text = await r.text()
      loadFromYaml(text)
      setEditMode(false)
      setError(null)
    } catch (e) {
      setError(`Load failed: ${e}`)
    }
  }

  // ── Render ──────────────────────────────────────────────────────────────

  return (
    <div className={css.yamlTab}>
      <div className={css.yamlToolbar}>
        {editMode ? (
          <>
            <button className={css.yamlBtnPrimary} onClick={applyEdit}
              title="Parse and apply to state (Ctrl+Enter)">Apply</button>
            <button className={css.yamlBtn} onClick={discardEdit}>Discard</button>
          </>
        ) : (
          <button className={css.yamlBtn} onClick={enterEdit}
            title="Edit YAML manually">Edit</button>
        )}
        <div className={css.yamlToolbarSep} />
        <button className={css.yamlBtn} onClick={copyToClipboard}>Copy</button>
        <button className={css.yamlBtn} onClick={downloadFile}>Download</button>
        <button className={css.yamlBtn} onClick={openFilePicker}>Open file…</button>
        <button className={css.yamlBtn} onClick={loadFromServer}>From server</button>
        {editMode && (
          <span className={css.yamlEditBadge}>EDITING</span>
        )}
      </div>

      {error && <div className={css.yamlError}>{error}</div>}

      <textarea
        className={css.yamlArea}
        value={editMode ? editText : liveYaml}
        readOnly={!editMode}
        onChange={editMode ? e => setEditText(e.target.value) : undefined}
        onKeyDown={editMode ? e => {
          if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
            e.preventDefault()
            applyEdit()
          }
          if (e.key === 'Escape') discardEdit()
        } : undefined}
        spellCheck={false}
      />

      <input
        ref={fileInputRef}
        type="file"
        accept=".yaml,.yml"
        style={{ display: 'none' }}
        onChange={handleFileChange}
      />
    </div>
  )
}
