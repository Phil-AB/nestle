"use client"

import { ContentBlock } from "@/lib/api-client"
import { bboxToPixels, getBlockColor, getBlockBorderColor } from "@/lib/coordinate-utils"

interface AnnotationOverlayProps {
  blocks: ContentBlock[]
  containerWidth: number
  containerHeight: number
  currentPage?: number
  onBlockClick?: (blockIndex: number) => void
  highlightedBlockIndex?: number
}

export function AnnotationOverlay({
  blocks,
  containerWidth,
  containerHeight,
  currentPage = 1,
  onBlockClick,
  highlightedBlockIndex,
}: AnnotationOverlayProps) {
  // Filter blocks for current page
  const pageBlocks = blocks.filter(
    (block) => !block.bbox?.page || block.bbox.page === currentPage
  )

  return (
    <div
      className="absolute inset-0 pointer-events-none"
      style={{ width: containerWidth, height: containerHeight }}
    >
      {pageBlocks.map((block, idx) => {
        if (!block.bbox) return null

        const pixelBox = bboxToPixels(block.bbox, containerWidth, containerHeight)
        const isHighlighted = highlightedBlockIndex === idx

        return (
          <div
            key={idx}
            className="absolute pointer-events-auto cursor-pointer transition-all hover:opacity-80"
            style={{
              left: pixelBox.x,
              top: pixelBox.y,
              width: pixelBox.width,
              height: pixelBox.height,
              backgroundColor: getBlockColor(block.type),
              border: `2px solid ${getBlockBorderColor(block.type)}`,
              borderWidth: isHighlighted ? '3px' : '2px',
              opacity: isHighlighted ? 1 : 0.6,
              zIndex: isHighlighted ? 20 : 10,
            }}
            onClick={() => onBlockClick?.(idx)}
            title={`${block.type}: ${block.content.substring(0, 50)}...`}
          />
        )
      })}
    </div>
  )
}
