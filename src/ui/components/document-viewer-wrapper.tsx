"use client"

import { PDFViewer } from "./pdf-viewer"
import { ImageViewer } from "./image-viewer"
import { ContentBlock } from "@/lib/api-client"
import { AlertCircle } from "lucide-react"
import { Card } from "./ui/card"

interface DocumentViewerWrapperProps {
  fileUrl: string
  fileType: string
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
  const isPDF = fileType === "application/pdf" || fileUrl.toLowerCase().endsWith(".pdf")
  const isImage = fileType.startsWith("image/") || /\.(png|jpg|jpeg|tiff)$/i.test(fileUrl) || fileType === "auto-detect"

  // Ensure blocks is always an array, never null or undefined
  const safeBlocks = blocks || []

  if (isPDF) {
    return (
      <PDFViewer
        fileUrl={fileUrl}
        blocks={safeBlocks}
        onBlockClick={onBlockClick}
        highlightedBlockIndex={highlightedBlockIndex}
      />
    )
  }

  if (isImage) {
    return (
      <ImageViewer
        fileUrl={fileUrl}
        blocks={safeBlocks}
        onBlockClick={onBlockClick}
        highlightedBlockIndex={highlightedBlockIndex}
      />
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
