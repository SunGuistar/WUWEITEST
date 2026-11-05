import { useCallback, useRef, useState } from 'react'

const ASSETS = {
  illustration: '/assets/images/1-21_illustration-resume-scene.png',
  cloudIcon: '/assets/svg/1-27_icon-upload-cloud.svg',
  dotOuter: '/assets/svg/1-31_step-dot-1-outer.svg',
  dotInner: '/assets/svg/1-34_step-dot-1-inner.svg',
  check: '/assets/svg/1-35_icon-check-1.svg',
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

function StepDots() {
  return (
    <div className="progress" aria-label="Progress: step 3 of 3">
      <div className="progress__track" aria-hidden="true">
        <div className="progress__track-active" />
      </div>
      {[1, 2, 3].map((step) => (
        <span className="dot" style={{ left: `${(step - 1) * 128 + 28}px` }} key={step}>
          <img className="dot__outer" src={ASSETS.dotOuter} alt="" aria-hidden="true" />
          <span className="dot__inner">
            <img src={ASSETS.dotInner} alt="" aria-hidden="true" />
            {step < 3 ? (
              <img className="dot__check" src={ASSETS.check} alt="" aria-hidden="true" />
            ) : (
              <span className="dot__number" aria-hidden="true">3</span>
            )}
          </span>
          <span className="sr-only">{step < 3 ? `Step ${step} done` : 'Step 3, current'}</span>
        </span>
      ))}
    </div>
  )
}

export default function App() {
  const inputRef = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null)
  const [dragOver, setDragOver] = useState(false)

  const openFileDialog = useCallback(() => {
    inputRef.current?.click()
  }, [])

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    const dropped = e.dataTransfer.files?.[0]
    if (dropped) setFile(dropped)
  }, [])

  return (
    <main className="page">
      <section className="upload-section" aria-labelledby="page-title">
        <div className="intro">
          <h1 id="page-title" className="intro__title">{'Finish!\nUpload Your Resume'}</h1>
          <p className="intro__desc">
            Upload your resume, the platform will help you parse and optimize, you
            can also skip this step
          </p>
          <img className="intro__illustration" src={ASSETS.illustration} alt="" aria-hidden="true" />
        </div>

        <section className="card" aria-label="Upload file card">
          <h2 className="card__title">Upload file</h2>

          <div
            className={`dropzone${dragOver ? ' dropzone--dragover' : ''}${file ? ' dropzone--has-file' : ''}`}
            role="button"
            tabIndex={0}
            aria-label={file ? `Selected file: ${file.name}. Activate to choose another file` : 'Drag your resume file to this area, or activate to select a file to upload'}
            onClick={openFileDialog}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault()
                openFileDialog()
              }
            }}
            onDragOver={(e) => {
              e.preventDefault()
              setDragOver(true)
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={onDrop}
          >
            <img className="dropzone__icon" src={ASSETS.cloudIcon} alt="" aria-hidden="true" />
            {file ? (
              <p className="dropzone__file" aria-live="polite">
                <span className="dropzone__file-name">{file.name}</span>
                <span className="dropzone__file-size">{formatSize(file.size)}</span>
              </p>
            ) : (
              <p className="dropzone__hint">
                Drag your resume file to this area, or click on the area to select
                the appropriate file to upload
              </p>
            )}
            <input
              ref={inputRef}
              type="file"
              className="sr-only"
              aria-hidden="true"
              tabIndex={-1}
              accept=".pdf,.doc,.docx,.txt,image/*"
              onChange={(e) => {
                const chosen = e.target.files?.[0]
                if (chosen) setFile(chosen)
              }}
            />
          </div>

          <div className="actions">
            <button type="button" className="btn btn--secondary">Last step</button>
            <button type="button" className="btn btn--primary">finish</button>
          </div>

          <StepDots />
        </section>
      </section>
    </main>
  )
}
