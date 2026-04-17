import { useEffect, useRef } from 'react'
import css from './Designer.module.css'
import Header from './Header'
import LeftPanel from './LeftPanel'
import Canvas from './Canvas'
import RightPanel from './RightPanel'
import PickBanner from './PickBanner'
import StatusBar from './StatusBar'
import RunPanel from './RunPanel'
import PortAssignView from './PortAssignView'
import { useDesignerStore } from '../../store/designerStore'

export default function Designer() {
  const pickState      = useDesignerStore(s => s.pickState)
  const showRunPanel   = useDesignerStore(s => s.showRunPanel)
  const portAssignTarget = useDesignerStore(s => s.portAssignTarget)
  const selectedDevRef = useDesignerStore(s => s.selectedDevRef)
  const exitPickMode   = useDesignerStore(s => s.exitPickMode)
  const selectDevice   = useDesignerStore(s => s.selectDevice)
  const removeDevice   = useDesignerStore(s => s.removeDevice)
  const undo           = useDesignerStore(s => s.undo)
  const redo           = useDesignerStore(s => s.redo)
  const version        = useDesignerStore(s => s.version)
  const setSaveStatus  = useDesignerStore(s => s.setSaveStatus)
  const generateYaml   = useDesignerStore(s => s.generateYaml)
  const loadFromYaml   = useDesignerStore(s => s.loadFromYaml)

  // Suppress the auto-save that would otherwise fire immediately after loading from server
  const skipNextSave = useRef(false)

  // Load latest YAML from server on first mount
  useEffect(() => {
    fetch('/yaml')
      .then(r => r.ok ? r.text() : Promise.reject(r.status))
      .then(text => {
        skipNextSave.current = true
        loadFromYaml(text)
        setSaveStatus('saved')
      })
      .catch(() => {})  // server not reachable — start with empty state
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // Debounced auto-save to server — fires 1.5 s after the last state change
  useEffect(() => {
    if (version === 0) return          // skip initial mount
    if (skipNextSave.current) { skipNextSave.current = false; return }
    setSaveStatus('unsaved')
    const timer = setTimeout(async () => {
      setSaveStatus('saving')
      try {
        const yaml = generateYaml()
        const r = await fetch('/yaml', {
          method:  'POST',
          headers: { 'Content-Type': 'text/plain' },
          body:    yaml,
        })
        setSaveStatus(r.ok ? 'saved' : 'error')
      } catch {
        // Server not reachable — silently revert so we don't alarm the user
        setSaveStatus('idle')
      }
    }, 1500)
    return () => clearTimeout(timer)
  }, [version]) // eslint-disable-line react-hooks/exhaustive-deps

  // Keyboard shortcuts
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      // Undo / redo — allowed even when an input is focused
      if (e.ctrlKey || e.metaKey) {
        if (e.key === 'z' && !e.shiftKey) { e.preventDefault(); undo(); return }
        if (e.key === 'y' || (e.key === 'z' && e.shiftKey)) { e.preventDefault(); redo(); return }
      }

      // Ignore remaining shortcuts when typing in inputs
      const tag = (e.target as HTMLElement).tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return

      if (e.key === 'Escape') {
        if (pickState) {
          exitPickMode()
        } else {
          selectDevice(null)
        }
      }

      if (e.key === 'Delete' || e.key === 'Backspace') {
        if (selectedDevRef) {
          removeDevice(selectedDevRef.rackId, selectedDevRef.face, selectedDevRef.dev.name)
          selectDevice(null)
        }
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [pickState, selectedDevRef, exitPickMode, selectDevice, removeDevice, undo, redo])

  return (
    <div className={css.root}>
      <Header />
      {pickState && <PickBanner />}
      <div className={css.body}>
        <LeftPanel />
        <Canvas />
        <RightPanel />
      </div>
      {showRunPanel && <RunPanel />}
      <StatusBar />
      {portAssignTarget && <PortAssignView />}
    </div>
  )
}
