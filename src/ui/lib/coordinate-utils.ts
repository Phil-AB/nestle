/**
 * Coordinate transformation utilities for document annotations.
 * Converts normalized bounding boxes (0-1) to pixel coordinates.
 */

export interface BoundingBox {
  left: number    // 0-1 normalized
  top: number     // 0-1 normalized
  width: number   // 0-1 normalized
  height: number  // 0-1 normalized
  page?: number
}

export interface PixelBox {
  x: number       // pixels from left
  y: number       // pixels from top
  width: number   // pixels
  height: number  // pixels
}

/**
 * Convert normalized bbox (0-1) to pixel coordinates
 */
export function bboxToPixels(
  bbox: BoundingBox,
  containerWidth: number,
  containerHeight: number
): PixelBox {
  return {
    x: bbox.left * containerWidth,
    y: bbox.top * containerHeight,
    width: bbox.width * containerWidth,
    height: bbox.height * containerHeight,
  }
}

/**
 * Get color for block type (used for annotation highlighting)
 */
export function getBlockColor(blockType: string): string {
  const colors: Record<string, string> = {
    'Title': 'rgba(59, 130, 246, 0.3)',        // blue
    'Section Header': 'rgba(139, 92, 246, 0.3)', // purple
    'Key Value': 'rgba(34, 197, 94, 0.3)',     // green
    'Text': 'rgba(251, 146, 60, 0.3)',         // orange
    'Figure': 'rgba(236, 72, 153, 0.3)',       // pink
  }
  return colors[blockType] || 'rgba(156, 163, 175, 0.3)' // gray default
}

/**
 * Get border color for block type
 */
export function getBlockBorderColor(blockType: string): string {
  const colors: Record<string, string> = {
    'Title': '#3b82f6',
    'Section Header': '#8b5cf6',
    'Key Value': '#22c55e',
    'Text': '#fb923c',
    'Figure': '#ec4899',
  }
  return colors[blockType] || '#9ca3af'
}
