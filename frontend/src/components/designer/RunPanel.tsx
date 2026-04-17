import { useRef, useEffect } from 'react'
import css from './RunPanel.module.css'
import { useDesignerStore } from '../../store/designerStore'

const PNG_SECTIONS = [
  { key: 'rack',   label: 'Rack Diagrams' },
  { key: 'wiring', label: 'Wiring Diagrams' },
  { key: 'ports',  label: 'Port Schedules' },
] as const

function logClass(line: string): string {
  if (/error|fail|exception/i.test(line)) return css.logErr
  if (/done|complete|ok\]/i.test(line))   return css.logDone
  if (/warning|warn/i.test(line))         return css.logWarn
  return css.logInfo
}

export default function RunPanel() {
  const runLog       = useDesignerStore(s => s.runLog)
  const runFiles     = useDesignerStore(s => s.runFiles)
  const isRunning    = useDesignerStore(s => s.isRunning)
  const togglePanel  = useDesignerStore(s => s.toggleRunPanel)

  const logRef = useRef<HTMLDivElement>(null)

  // Auto-scroll log to bottom
  useEffect(() => {
    const el = logRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [runLog])

  const statusText = isRunning ? 'Running...' : runLog.length ? 'Done' : 'Idle'
  const statusClass = isRunning ? css.statusRunning : runLog.some(l => /error|fail/i.test(l)) ? css.statusError : css.statusDone

  return (
    <div className={css.panel}>
      {/* Header */}
      <div className={css.panelHeader}>
        <span className={css.panelTitle}>▶ Pipeline Output</span>
        <span className={`${css.statusBadge} ${statusClass}`}>{statusText}</span>
        <button className={css.closeBtn} onClick={togglePanel} title="Close panel">×</button>
      </div>

      <div className={css.panelBody}>
        {/* Log pane */}
        <div className={css.logPane} ref={logRef}>
          {runLog.length === 0 && (
            <div className={css.logEmpty}>No output yet.</div>
          )}
          {runLog.map((line, i) => (
            <div key={i} className={`${css.logLine} ${logClass(line)}`}>{line}</div>
          ))}
        </div>

        {/* Files pane */}
        <div className={css.filesPane}>
          <div className={css.filesPaneTitle}>Output Files</div>

          {!runFiles && (
            <div className={css.noFiles}>{isRunning ? 'Running...' : 'No output yet.'}</div>
          )}

          {runFiles && (
            <>
              {/* PNG thumbnails */}
              {PNG_SECTIONS.map(sec => {
                const files = runFiles.pngs[sec.key]
                if (!files?.length) return null
                return (
                  <div key={sec.key} className={css.pngSection}>
                    <div className={css.pngSectionTitle}>{sec.label}</div>
                    <div className={css.pngGrid}>
                      {files.map(f => (
                        <a
                          key={f}
                          href={`/pngs/${sec.key}/${f}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className={css.pngThumb}
                          title={f}
                        >
                          <img
                            src={`/pngs/${sec.key}/${f}`}
                            alt={f}
                            className={css.pngImg}
                          />
                          <span className={css.pngName}>{f.replace(/\.[^.]+$/, '')}</span>
                        </a>
                      ))}
                    </div>
                  </div>
                )
              })}

              {/* Other output files */}
              {runFiles.output.filter(f => !f.endsWith('.dot')).length > 0 && (
                <div className={css.pngSection}>
                  <div className={css.pngSectionTitle}>Data Files</div>
                  <div className={css.dataFiles}>
                    {runFiles.output.filter(f => !f.endsWith('.dot')).map(f => {
                      const ext = f.split('.').pop()?.toLowerCase() ?? ''
                      const icon = ext === 'csv' ? '📊' : ext === 'html' ? '🌐' : ext === 'pdf' ? '📄' : '📁'
                      return (
                        <a
                          key={f}
                          href={`/output/${f}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className={css.dataFile}
                        >
                          <span>{icon}</span>
                          <span>{f}</span>
                        </a>
                      )
                    })}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}
