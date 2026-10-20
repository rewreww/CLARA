import { useEffect, useRef, useState } from 'react'
import { ChevronLeft, ChevronRight, ExternalLink, LoaderCircle, Minus, Plus, RotateCcw } from 'lucide-react'
import * as pdfjs from 'pdfjs-dist'
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url'
import { citationPage, sourceDocumentUrl } from '../lib/sources'

pdfjs.GlobalWorkerOptions.workerSrc = workerUrl

export default function PdfPreview({ source, patientId }) {
  const citedPage = citationPage(source)
  const url = sourceDocumentUrl(source, patientId)
  const [document, setDocument] = useState(null)
  const [page, setPage] = useState(citedPage || 1)
  const [zoom, setZoom] = useState(1)
  const [width, setWidth] = useState(300)
  const [busy, setBusy] = useState(true)
  const [error, setError] = useState('')
  const [retry, setRetry] = useState(0)
  const viewport = useRef(null)
  const canvasHost = useRef(null)

  useEffect(() => {
    const observer = new ResizeObserver(entries => setWidth(Math.max(160, entries[0].contentRect.width - 24)))
    if (viewport.current) observer.observe(viewport.current)
    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    setDocument(null); setError(''); setBusy(true)
    if (!url) { setError('This source has no available PDF.'); setBusy(false); return }
    let cancelled = false
    const task = pdfjs.getDocument({ url, isEvalSupported: false })
    task.promise.then(pdf => { if (!cancelled) setDocument(pdf) }).catch(() => {
      if (!cancelled) { setError('The source PDF could not be loaded. It may have moved or the document service may be offline.'); setBusy(false) }
    })
    return () => { cancelled = true; task.destroy().catch(() => {}) }
  }, [url, retry])

  useEffect(() => {
    if (!document) return
    setBusy(true); setError('')
    let cancelled = false, renderTask
    if (page > document.numPages) { setError(`Cited page ${page} is not present in this ${document.numPages}-page PDF.`); setBusy(false); return }
    const render = async () => {
      try {
        const pdfPage = await document.getPage(page)
        if (cancelled) return
        const scale = width / pdfPage.getViewport({ scale: 1 }).width * zoom
        const view = pdfPage.getViewport({ scale })
        const ratio = Math.min(window.devicePixelRatio || 1, 2)
        const canvas = window.document.createElement('canvas')
        canvas.width = Math.ceil(view.width * ratio); canvas.height = Math.ceil(view.height * ratio)
        canvas.style.width = `${view.width}px`; canvas.style.height = `${view.height}px`
        canvas.setAttribute('role', 'img'); canvas.setAttribute('aria-label', `${source.title || source.source}, page ${page}`)
        renderTask = pdfPage.render({ canvasContext: canvas.getContext('2d'), viewport: view, transform: [ratio, 0, 0, ratio, 0, 0] })
        await renderTask.promise
        if (!cancelled) { canvasHost.current?.replaceChildren(canvas); setBusy(false) }
      } catch (failure) {
        if (!cancelled && failure.name !== 'RenderingCancelledException') { setError('This PDF page could not be rendered.'); setBusy(false) }
      }
    }
    render()
    return () => { cancelled = true; renderTask?.cancel() }
  }, [document, page, width, zoom, source])

  return <div className="pdf-preview">
    <div className="pdf-document-title" title={source.source}>{source.title || source.source}</div>
    <div className="pdf-citation-label">{citedPage ? `Cited PDF page ${citedPage}` : 'No page number supplied by this citation'}</div>
    <div className="pdf-toolbar">
      <button className="icon-button" aria-label="Previous PDF page" title="Previous page" disabled={!document || page <= 1} onClick={() => setPage(value => value - 1)}><ChevronLeft size={16} /></button>
      <span className="pdf-page-count" aria-live="polite">{page} / {document?.numPages || '-'}</span>
      <button className="icon-button" aria-label="Next PDF page" title="Next page" disabled={!document || page >= document.numPages} onClick={() => setPage(value => value + 1)}><ChevronRight size={16} /></button>
      <span className="toolbar-spacer" />
      <button className="icon-button" aria-label="Zoom out PDF" title="Zoom out" disabled={zoom <= .75} onClick={() => setZoom(value => Math.max(.75, value - .25))}><Minus size={15} /></button>
      <button className="icon-button" aria-label="Fit PDF width" title="Fit width" onClick={() => setZoom(1)}><RotateCcw size={14} /></button>
      <button className="icon-button" aria-label="Zoom in PDF" title="Zoom in" disabled={zoom >= 2.5} onClick={() => setZoom(value => Math.min(2.5, value + .25))}><Plus size={15} /></button>
    </div>
    {citedPage && page !== citedPage && <button className="return-citation" onClick={() => setPage(citedPage)}>Return to cited page {citedPage}</button>}
    <div className="pdf-viewport" ref={viewport} aria-busy={busy}>
      {busy && <div className="pdf-state" role="status"><LoaderCircle size={22} className="spin-icon" />Loading PDF page...</div>}
      {error && <div className="pdf-state" role="alert"><p>{error}</p><button className="text-button" onClick={() => setRetry(value => value + 1)}>Retry</button></div>}
      <div className="pdf-canvas-host" ref={canvasHost} hidden={busy || !!error} />
    </div>
    {url && <a className="open-pdf" href={`${url}#page=${page}`} target="_blank" rel="noopener noreferrer"><ExternalLink size={15} />Open PDF in new tab</a>}
  </div>
}
