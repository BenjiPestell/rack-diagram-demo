import { useRef, useState } from 'react'
import css from './Tabs.module.css'
import { useDesignerStore } from '../../../store/designerStore'

export default function YAMLTab() {
  const generateYaml = useDesignerStore(s => s.generateYaml)
  const loadFromYaml = useDesignerStore(s => s.loadFromYaml)

  const [yamlText, setYamlText] = useState(() => generateYaml())
  const [error, setError]       = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  function refresh() {
    setYamlText(generateYaml())
    setError(null)
  }

  function apply() {
    try {
      loadFromYaml(yamlText)
      setError(null)
    } catch (e) {
      setError(String(e))
    }
  }

  async function saveToServer() {
    try {
      const r = await fetch('/yaml', {
        method: 'POST',
        headers: { 'Content-Type': 'text/plain' },
        body: yamlText,
      })
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
    } catch (e) {
      setError(`Save failed: ${e}`)
    }
  }

  async function loadFromServer() {
    try {
      const r = await fetch('/yaml')
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      const text = await r.text()
      setYamlText(text)
      setError(null)
    } catch (e) {
      setError(`Load failed: ${e}`)
    }
  }

  function copyToClipboard() {
    navigator.clipboard.writeText(yamlText).catch(() => {})
  }

  function downloadFile() {
    const blob = new Blob([yamlText], { type: 'text/yaml' })
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
      setYamlText(text)
      setError(null)
    }
    reader.readAsText(file)
    // Reset so the same file can be picked again
    e.target.value = ''
  }

  return (
    <div className={css.yamlTab}>
      <div className={css.yamlToolbar}>
        <button className={css.yamlBtn} onClick={refresh} title="Regenerate YAML from current state">Refresh</button>
        <button className={css.yamlBtn} onClick={apply} title="Parse textarea and apply to state">Apply</button>
        <button className={css.yamlBtn} onClick={loadFromServer}>From server</button>
        <button className={css.yamlBtn} onClick={saveToServer}>To server</button>
        <button className={css.yamlBtn} onClick={copyToClipboard}>Copy</button>
        <button className={css.yamlBtn} onClick={openFilePicker}>Open file…</button>
        <button className={css.yamlBtn} onClick={downloadFile}>Download</button>
      </div>
      {error && <div className={css.yamlError}>{error}</div>}
      <textarea
        className={css.yamlArea}
        value={yamlText}
        onChange={e => setYamlText(e.target.value)}
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
