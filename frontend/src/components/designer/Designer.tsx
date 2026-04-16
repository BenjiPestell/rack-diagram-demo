import { useEffect } from 'react'
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
