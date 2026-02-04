"use client"

import { useState } from "react"
import { PDFViewer } from "./pdf-viewer"
import { ImageViewer } from "./image-viewer"
import { ContentBlock } from "@/lib/api-client"
import { AlertCircle, ToggleLeft, ToggleRight } from "lucide-react"
import { Card } from "./ui/card"
import { Button } from "./ui/button"

interface DocumentViewerWrapperProps {
  fileUrl: string
  fileType?: string
  blocks?: ContentBlock[]
  onBlockClick?: (blockIndex: number) => void
  highlightedBlockIndex?: number
}

export function DocumentViewerWrapper({
  fileUrl,
  fileType,
  blocks,
  onBlockClick,
  highlightedBlockIndex,
}: DocumentViewerWrapperProps) {
  const [showAnnotations, setShowAnnotations] = useState(false)

  // If mime_type is not provided, fall back to extension detection
  const isPDF = fileType === "application/pdf" || (!fileType && fileUrl.toLowerCase().endsWith(".pdf"))
  const isImage = fileType?.startsWith("image/") || (!fileType && /\.(png|jpg|jpeg|tiff)$/i.test(fileUrl))

  const hasAnnotations = blocks && blocks.length > 0

  // Ensure blocks is always an array, never null or undefined
  const safeBlocks = blocks || []

  const AnnotationToggle = () => (
    hasAnnotations ? (
      <div className="flex items-center justify-end mb-4">
        <Button
          variant="outline"
          size="sm"
          onClick={() => setShowAnnotations(!showAnnotations)}
          className="flex items-center gap-2"
        >
          {showAnnotations ? (
            <>
              <ToggleRight className="w-4 h-4 text-primary" />
              <span>Annotations On</span>
            </>
          ) : (
            <>
              <ToggleLeft className="w-4 h-4 text-muted-foreground" />
              <span>Annotations Off</span>
            </>
          )}
        </Button>
      </div>
    ) : null
  )

  if (isPDF) {
    return (
      <div>
        <AnnotationToggle />
        <PDFViewer
          fileUrl={fileUrl}
          blocks={safeBlocks}
          onBlockClick={onBlockClick}
          highlightedBlockIndex={highlightedBlockIndex}
          showAnnotations={showAnnotations}
        />
      </div>
    )
  }

  if (isImage) {
    return (
      <div>
        <AnnotationToggle />
        <ImageViewer
          fileUrl={fileUrl}
          blocks={safeBlocks}
          onBlockClick={onBlockClick}
          highlightedBlockIndex={highlightedBlockIndex}
          showAnnotations={showAnnotations}
        />
      </div>
    )
  }

  return (
    <Card className="p-8 text-center">
      <AlertCircle className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
      <h3 className="text-lg font-semibold mb-2">Unsupported File Type</h3>
      <p className="text-muted-foreground">
        This file type cannot be previewed. Supported formats: PDF, PNG, JPG, TIFF
      </p>
    </Card>
  )
}
