"use client"

import { useEffect, useRef, useState } from "react"
import { Button } from "@/components/ui/button"
import { ZoomIn, ZoomOut, ChevronLeft, ChevronRight } from "lucide-react"
import { ContentBlock } from "@/lib/api-client"
import { AnnotationOverlay } from "./annotation-overlay"

interface PDFViewerProps {
  fileUrl: string
  blocks?: ContentBlock[]
  onBlockClick?: (blockIndex: number) => void
  highlightedBlockIndex?: number
}

export function PDFViewer({
  fileUrl,
  blocks = [],
  onBlockClick,
  highlightedBlockIndex,
}: PDFViewerProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  const [pdf, setPdf] = useState<any>(null)
  const [currentPage, setCurrentPage] = useState(1)
  const [totalPages, setTotalPages] = useState(0)
  const [scale, setScale] = useState(1.5)
  const [loading, setLoading] = useState(true)
  const [canvasSize, setCanvasSize] = useState({ width: 0, height: 0 })

  // Load PDF - client side only
  useEffect(() => {
    // Only run on client
    if (typeof window === 'undefined') return

    const loadPDF = async () => {
      try {
        setLoading(true)

        // Dynamic import PDF.js on client side
        const pdfjsLib = await import('pdfjs-dist')

        // Configure worker
        pdfjsLib.GlobalWorkerOptions.workerSrc = `https://unpkg.com/pdfjs-dist@${pdfjsLib.version}/build/pdf.worker.min.mjs`

        const loadingTask = pdfjsLib.getDocument(fileUrl)
        const pdfDoc = await loadingTask.promise
        setPdf(pdfDoc)
        setTotalPages(pdfDoc.numPages)
        setLoading(false)
      } catch (error) {
        console.error("Error loading PDF:", error)
        setLoading(false)
      }
    }
    loadPDF()
  }, [fileUrl])

  // Render page
  useEffect(() => {
    if (!pdf || !canvasRef.current) return

    const renderPage = async () => {
      const page = await pdf.getPage(currentPage)
      const viewport = page.getViewport({ scale })

      const canvas = canvasRef.current!
      const context = canvas.getContext("2d")!

      canvas.width = viewport.width
      canvas.height = viewport.height
      setCanvasSize({ width: viewport.width, height: viewport.height })

      await page.render({
        canvasContext: context,
        viewport: viewport,
      }).promise
    }

    renderPage()
  }, [pdf, currentPage, scale])

  const zoomIn = () => setScale((s) => Math.min(s + 0.25, 3))
  const zoomOut = () => setScale((s) => Math.max(s - 0.25, 0.5))
  const nextPage = () => setCurrentPage((p) => Math.min(p + 1, totalPages))
  const prevPage = () => setCurrentPage((p) => Math.max(p - 1, 1))

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary" />
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Controls */}
      <div className="flex items-center justify-between bg-muted p-4 rounded-lg">
        <div className="flex items-center gap-2">
          <Button
            onClick={prevPage}
            disabled={currentPage === 1}
            size="sm"
            variant="outline"
          >
            <ChevronLeft className="w-4 h-4" />
          </Button>
          <span className="text-sm font-medium min-w-[100px] text-center">
            Page {currentPage} of {totalPages}
          </span>
          <Button
            onClick={nextPage}
            disabled={currentPage === totalPages}
            size="sm"
            variant="outline"
          >
            <ChevronRight className="w-4 h-4" />
          </Button>
        </div>
        <div className="flex items-center gap-2">
          <Button onClick={zoomOut} size="sm" variant="outline">
            <ZoomOut className="w-4 h-4" />
          </Button>
          <span className="text-sm font-medium min-w-[60px] text-center">
            {Math.round(scale * 100)}%
          </span>
          <Button onClick={zoomIn} size="sm" variant="outline">
            <ZoomIn className="w-4 h-4" />
          </Button>
        </div>
      </div>

      {/* PDF Canvas with Annotations */}
      <div
        ref={containerRef}
        className="relative border rounded-lg overflow-auto bg-gray-100"
        style={{ maxHeight: "70vh" }}
      >
        <canvas ref={canvasRef} className="mx-auto" />
        {canvasSize.width > 0 && (
          <AnnotationOverlay
            blocks={blocks}
            containerWidth={canvasSize.width}
            containerHeight={canvasSize.height}
            currentPage={currentPage}
            onBlockClick={onBlockClick}
            highlightedBlockIndex={highlightedBlockIndex}
          />
        )}
      </div>
    </div>
  )
}
