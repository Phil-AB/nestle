"use client"

import { useState, useEffect, useRef } from "react"
import { Button } from "@/components/ui/button"
import { ZoomIn, ZoomOut, AlertCircle, Loader2, Maximize2 } from "lucide-react"
import { ContentBlock } from "@/lib/api-client"
import { AnnotationOverlay } from "./annotation-overlay"

interface ImageViewerProps {
  fileUrl: string
  blocks?: ContentBlock[]
  onBlockClick?: (blockIndex: number) => void
  highlightedBlockIndex?: number
  showAnnotations?: boolean
}

export function ImageViewer({
  fileUrl,
  blocks = [],
  onBlockClick,
  highlightedBlockIndex,
  showAnnotations = true,
}: ImageViewerProps) {
  const [scale, setScale] = useState(1)
  const [imageDimensions, setImageDimensions] = useState({ width: 0, height: 0 })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const [initialScale, setInitialScale] = useState(1)

  const zoomIn = () => setScale((s) => Math.min(s + 0.25, 3))
  const zoomOut = () => setScale((s) => Math.max(s - 0.25, 0.25))
  const resetZoom = () => setScale(initialScale)

  // Calculate initial scale to fit image in viewport
  useEffect(() => {
    if (containerRef.current && imageDimensions.width > 0 && imageDimensions.height > 0) {
      const container = containerRef.current
      const containerWidth = container.clientWidth - 32 // Account for padding
      const containerHeight = Math.min(800, window.innerHeight - 300) // Max height for viewport

      const scaleX = containerWidth / imageDimensions.width
      const scaleY = containerHeight / imageDimensions.height
      const fitScale = Math.min(scaleX, scaleY, 1) // Don't scale up beyond original size

      setInitialScale(fitScale)
      setScale(fitScale)
    }
  }, [imageDimensions])

  return (
    <div className="flex flex-col gap-4">
      {/* Controls */}
      <div className="flex items-center justify-between bg-muted p-4 rounded-lg">
        <div className="text-sm text-muted-foreground">
          {imageDimensions.width > 0 && (
            <span>
              Original: {imageDimensions.width} × {imageDimensions.height}px
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <Button onClick={zoomOut} size="sm" variant="outline" disabled={scale <= 0.25}>
            <ZoomOut className="w-4 h-4" />
          </Button>
          <span className="text-sm font-medium min-w-[60px] text-center">
            {Math.round(scale * 100)}%
          </span>
          <Button onClick={zoomIn} size="sm" variant="outline" disabled={scale >= 3}>
            <ZoomIn className="w-4 h-4" />
          </Button>
          <Button onClick={resetZoom} size="sm" variant="outline" title="Fit to view">
            <Maximize2 className="w-4 h-4" />
          </Button>
        </div>
      </div>

      {/* Image with Annotations */}
      <div 
        ref={containerRef}
        className="relative w-full min-h-[500px] border-2 border-border rounded-lg overflow-auto bg-gray-50"
      >
        {/* Loading State */}
        {loading && !error && (
          <div className="absolute inset-0 flex items-center justify-center bg-gray-50">
            <div className="text-center">
              <Loader2 className="w-12 h-12 animate-spin text-primary mx-auto mb-4" />
              <p className="text-sm text-muted-foreground">Loading document...</p>
            </div>
          </div>
        )}

        {/* Error State */}
        {error && (
          <div className="absolute inset-0 flex items-center justify-center bg-gray-50">
            <div className="text-center p-8">
              <AlertCircle className="w-12 h-12 text-destructive mx-auto mb-4" />
              <h3 className="text-lg font-semibold mb-2">Failed to Load Image</h3>
              <p className="text-sm text-muted-foreground mb-2">{error}</p>
              <p className="text-xs text-muted-foreground font-mono break-all">URL: {fileUrl}</p>
            </div>
          </div>
        )}

        <div className="relative w-full p-4 flex justify-center">
          <div
            className="relative"
            style={{
              width: imageDimensions.width > 0 ? `${imageDimensions.width * scale}px` : 'auto',
              height: imageDimensions.height > 0 ? `${imageDimensions.height * scale}px` : 'auto',
            }}
          >
            <img
              src={fileUrl}
              alt="Document"
              className="block"
              style={{
                width: imageDimensions.width > 0 ? `${imageDimensions.width * scale}px` : 'auto',
                height: imageDimensions.height > 0 ? `${imageDimensions.height * scale}px` : 'auto',
                display: loading ? 'none' : 'block',
              }}
              onLoad={(e) => {
                const img = e.target as HTMLImageElement
                setImageDimensions({
                  width: img.naturalWidth,
                  height: img.naturalHeight,
                })
                setLoading(false)
                setError(null)
              }}
              onError={(e) => {
                console.error("Failed to load document image:", fileUrl)
                setLoading(false)
                setError("Failed to load document image. The file may not exist or there may be a network issue.")
              }}
            />
            {imageDimensions.width > 0 && blocks && blocks.length > 0 && !loading && showAnnotations && (
              <AnnotationOverlay
                blocks={blocks}
                containerWidth={imageDimensions.width * scale}
                containerHeight={imageDimensions.height * scale}
                onBlockClick={onBlockClick}
                highlightedBlockIndex={highlightedBlockIndex}
              />
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
