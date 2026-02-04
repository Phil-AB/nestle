"use client"

import React, { useState, useMemo, useCallback, useEffect, useRef } from 'react'
import { ZoomIn, ZoomOut, RotateCw, ChevronLeft, ChevronRight, Save, X, CheckCircle } from 'lucide-react'
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Card } from "@/components/ui/card"
import { useToast } from "@/hooks/use-toast"
import { apiClient } from "@/lib/api-client"

interface BBox {
  left: number
  top: number
  width: number
  height: number
  page: number
}

interface Block {
  type: string
  bbox?: BBox
  content?: string
  confidence?: string
  image_url?: string | null
}

interface RawReductoResponse {
  result: {
    chunks: Array<{
      blocks: Block[]
    }>
  }
  usage?: {
    num_pages: number
  }
}

interface BBoxDocumentRendererProps {
  rawData: RawReductoResponse
  className?: string
  documentId?: string
}

/**
 * Escape HTML special characters to prevent XSS attacks
 * @param text - Raw text content that may contain HTML characters
 * @returns Sanitized text safe for HTML insertion
 */
function escapeHtml(text: string): string {
  const htmlEscapeMap: Record<string, string> = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#x27;',
    '/': '&#x2F;'
  }

  return text.replace(/[&<>"'\/]/g, (char) => htmlEscapeMap[char] || char)
}

/**
 * Sanitize HTML content by removing scripts and dangerous attributes
 * This provides defense-in-depth for contentEditable elements
 * @param html - HTML string that may contain malicious content
 * @returns Sanitized HTML safe for rendering
 */
function sanitizeHtml(html: string): string {
  // Remove script tags and their content
  let sanitized = html.replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '')

  // Remove event handler attributes (onclick, onerror, etc.)
  sanitized = sanitized.replace(/\s*on\w+\s*=\s*["'][^"']*["']/gi, '')
  sanitized = sanitized.replace(/\s*on\w+\s*=\s*[^\s>]*/gi, '')

  // Remove javascript: protocol
  sanitized = sanitized.replace(/javascript:/gi, '')

  // Remove data: protocol (can be used for XSS)
  sanitized = sanitized.replace(/data:text\/html/gi, '')

  return sanitized
}

/**
 * Convert markdown table to HTML table with XSS protection
 * Handles both markdown format and already-converted HTML from contentEditable
 * @param content - Markdown formatted table string or HTML table
 * @returns Sanitized HTML table or original content if not a valid table
 */
function markdownTableToHTML(content: string): string {
  try {
    // Check if content is already HTML (from contentEditable)
    if (content.trim().startsWith('<table')) {
      // Content is already HTML, just sanitize it
      return sanitizeHtml(content)
    }

    const lines = content.trim().split('\n').filter(line => line.trim())

    if (lines.length < 2) return escapeHtml(content) // Not a valid table, return escaped

    // Check if it's a markdown table (has pipes)
    // Note: Allow <br> tags in content since OCR often includes them
    if (!lines[0].includes('|')) return escapeHtml(content)

    const parseRow = (row: string) => {
      return row
        .split('|')
        .map(cell => cell.trim())
        .filter((cell, index, array) => {
          // Remove empty cells at start/end (from leading/trailing pipes)
          return !(cell === '' && (index === 0 || index === array.length - 1))
        })
    }

    const headers = parseRow(lines[0])
    const rows: string[][] = []

    // Skip separator line (|-|-|-|) and parse data rows
    for (let i = 1; i < lines.length; i++) {
      const line = lines[i].trim()
      if (line.match(/^\|[\s\-\|]+\|$/)) continue // Skip separator line
      rows.push(parseRow(line))
    }

    // Validate we have headers
    if (headers.length === 0) {
      return escapeHtml(content)
    }

    // Build HTML table with sanitized content
    let html = '<table class="border-collapse border border-black min-w-full table-fixed">'

    // Header - convert <br> to line breaks, then escape for XSS protection
    html += '<thead><tr class="even:bg-gray-300">'
    headers.forEach(header => {
      // Replace <br> variants with newlines before escaping
      const cleaned = header.replace(/<br\s*\/?>/gi, '\n')
      // Escape HTML but preserve newlines as <br> in output
      const escaped = escapeHtml(cleaned).replace(/\n/g, '<br>')
      html += `<th class="border border-black p-2 break-words">${escaped}</th>`
    })
    html += '</tr></thead>'

    // Body - convert <br> to line breaks, then escape for XSS protection
    html += '<tbody>'
    rows.forEach(row => {
      html += '<tr class="even:bg-gray-300">'
      row.forEach(cell => {
        // Replace <br> variants with newlines before escaping
        const cleaned = cell.replace(/<br\s*\/?>/gi, '\n')
        // Escape HTML but preserve newlines as <br> in output
        const escaped = escapeHtml(cleaned).replace(/\n/g, '<br>')
        html += `<td class="border border-black p-2 break-words">${escaped}</td>`
      })
      html += '</tr>'
    })
    html += '</tbody></table>'

    return html
  } catch (error) {
    // If parsing fails, return escaped content to prevent any injection
    console.error('Error parsing markdown table:', error)
    return escapeHtml(content)
  }
}

export function BBoxDocumentRenderer({ rawData, className = "", documentId }: BBoxDocumentRendererProps) {
  const [currentPage, setCurrentPage] = useState(1)
  const [scale, setScale] = useState(1)
  const [edits, setEdits] = useState<Record<string, string>>({})
  const [isSaving, setIsSaving] = useState(false)
  const [isApproving, setIsApproving] = useState(false)
  const { toast } = useToast()
  const containerRef = useRef<HTMLDivElement>(null)

  // Responsive page dimensions - calculated from content extent, adapts to container
  const { pageWidth, pageHeight } = useMemo(() => {
    const blocks = rawData?.result?.chunks?.flatMap(chunk => chunk.blocks || []) || []

    if (!blocks.length) return { pageWidth: 1000, pageHeight: 800 }

    // Find the maximum extent of content
    let maxWidth = 0
    let maxHeight = 0

    blocks.forEach(block => {
      if (block.bbox) {
        const right = block.bbox.left + block.bbox.width
        const bottom = block.bbox.top + block.bbox.height
        maxWidth = Math.max(maxWidth, right)
        maxHeight = Math.max(maxHeight, bottom)
      }
    })

    // Calculate responsive page size based on content extent
    // Use compact base values for tight rendering
    const baseWidth = 1000
    const baseHeight = 800

    return {
      pageWidth: Math.max(baseWidth, baseWidth * maxWidth),
      pageHeight: Math.max(baseHeight, baseHeight * maxHeight)
    }
  }, [rawData])

  // Auto-fit to container on mount and resize
  useEffect(() => {
    const handleResize = () => {
      if (containerRef.current) {
        const containerWidth = containerRef.current.clientWidth
        const availableWidth = containerWidth - 16 // Account for padding (8px each side)
        // Scale to fit width perfectly - no horizontal scroll
        const autoScale = availableWidth / pageWidth
        setScale(Math.max(0.3, autoScale)) // Minimum 30% to keep readable
      }
    }

    // Use timeout to ensure container is rendered
    const timeoutId = setTimeout(handleResize, 100)
    handleResize() // Also call immediately

    window.addEventListener('resize', handleResize)
    return () => {
      window.removeEventListener('resize', handleResize)
      clearTimeout(timeoutId)
    }
  }, [pageWidth])

  // Extract all blocks from raw data
  const allBlocks = useMemo(() => {
    if (!rawData?.result?.chunks) return []
    return rawData.result.chunks.flatMap(chunk => chunk.blocks || [])
  }, [rawData])

  const totalPages = rawData?.usage?.num_pages || 1

  // Filter blocks for current page
  const currentPageBlocks = useMemo(() =>
    allBlocks.filter(block =>
      block.bbox?.page === currentPage || (!block.bbox?.page && currentPage === 1)
    ),
    [allBlocks, currentPage]
  )

  // Get styling based on block type - consistent fonts with overflow handling
  const getBlockStyle = useCallback((block: Block, bbox: BBox) => {
    const baseStyle: React.CSSProperties = {
      position: 'absolute' as const,
      overflow: 'visible', // Allow content to render fully, bbox is approximate
      backgroundColor: 'white',
      border: 'none',
      boxSizing: 'border-box' as const,
      wordWrap: 'break-word' as const,
      overflowWrap: 'break-word' as const,
    }

    // Type-specific styling - readable font sizes
    switch (block.type) {
      case 'Title':
        return {
          ...baseStyle,
          fontSize: '16px',
          fontWeight: 'bold',
          display: 'block',
          textAlign: 'left' as const,
          padding: '4px 6px',
          lineHeight: '1.4',
          whiteSpace: 'normal' as const,
        }
      case 'Text':
        return {
          ...baseStyle,
          fontSize: '13px',
          display: 'flex',
          alignItems: 'flex-start',
          padding: '4px 6px',
          lineHeight: '1.5',
          whiteSpace: 'pre-wrap' as const,
        }
      case 'Table':
        return {
          ...baseStyle,
          fontSize: '13px',
          padding: '0px',
          lineHeight: '1.4',
          whiteSpace: 'pre-wrap' as const,
        }
      case 'Figure':
        return {
          ...baseStyle,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          backgroundColor: '#fafafa',
        }
      case 'Header':
      case 'Footer':
        return {
          ...baseStyle,
          fontSize: '12px',
          color: '#666',
          padding: '4px 6px',
          lineHeight: '1.4',
        }
      case 'Section Header':
        return {
          ...baseStyle,
          fontSize: '14px',
          fontWeight: '600',
          padding: '4px 6px',
          lineHeight: '1.4',
        }
      case 'Key Value':
        return {
          ...baseStyle,
          fontSize: '13px',
          padding: '4px 6px',
          lineHeight: '1.5',
          whiteSpace: 'pre-wrap' as const,
        }
      default:
        return {
          ...baseStyle,
          fontSize: '13px',
          padding: '4px 6px',
          lineHeight: '1.5',
          whiteSpace: 'pre-wrap' as const,
        }
    }
  }, [])

  const hasEdits = Object.keys(edits).length > 0

  // Handle content edit
  const handleContentEdit = (blockIndex: number, newContent: string) => {
    const blockKey = `block_${blockIndex}`
    setEdits(prev => ({
      ...prev,
      [blockKey]: newContent
    }))
  }

  // Handle save
  const handleSave = async () => {
    if (!documentId) {
      toast({
        title: "Save failed",
        description: "No document ID provided",
        variant: "destructive",
      })
      return
    }

    setIsSaving(true)
    try {
      await apiClient.updateDocumentFields(documentId, edits, {
        updated_by: "user",
        update_reason: "bbox_render_edit"
      })

      setEdits({})
      toast({
        title: "Changes saved",
        description: `Successfully updated ${Object.keys(edits).length} block(s)`,
        variant: "default",
      })
    } catch (error) {
      console.error('Failed to save edits:', error)
      toast({
        title: "Save failed",
        description: error instanceof Error ? error.message : "Failed to save changes",
        variant: "destructive",
      })
    } finally {
      setIsSaving(false)
    }
  }

  // Handle cancel
  const handleCancelEdits = () => {
    setEdits({})
  }

  // Handle approve - saves all data to database
  const handleApprove = async () => {
    if (!documentId) {
      toast({
        title: "Approval failed",
        description: "No document ID provided",
        variant: "destructive",
      })
      return
    }

    setIsApproving(true)
    try {
      // Collect all data from raw response with edits applied
      const allData: Record<string, any> = {
        blocks: allBlocks.map((block, idx) => {
          const blockKey = `block_${idx}`
          return {
            type: block.type,
            content: edits[blockKey] !== undefined ? edits[blockKey] : block.content,
            confidence: block.confidence,
            bbox: block.bbox,
            image_url: block.image_url
          }
        }),
        metadata: {
          document_id: documentId,
          approved_at: new Date().toISOString(),
          total_blocks: allBlocks.length,
          total_pages: totalPages
        }
      }

      // Save to database via API client
      await apiClient.approveDocument(documentId, allData)

      // Clear edits after successful approval
      setEdits({})

      toast({
        title: "Document approved",
        description: "All data has been saved to the database",
        variant: "default",
      })
    } catch (error) {
      console.error('Failed to approve document:', error)
      toast({
        title: "Approval failed",
        description: error instanceof Error ? error.message : "Failed to approve document",
        variant: "destructive",
      })
    } finally {
      setIsApproving(false)
    }
  }

  if (!rawData || allBlocks.length === 0) {
    return (
      <div className={`flex items-center justify-center h-full ${className}`}>
        <div className="text-center text-gray-500">
          <p className="text-lg font-medium">No document data</p>
          <p className="text-sm">Raw Reducto response is required</p>
        </div>
      </div>
    )
  }

  return (
    <div className={`flex flex-col h-full ${className}`}>
      {/* Global styles for table rendering */}
      <style dangerouslySetInnerHTML={{__html: `
        .table-container table {
          border-collapse: collapse !important;
          width: 100% !important;
          border: 1px solid #000 !important;
        }
        .table-container table td,
        .table-container table th {
          border: 1px solid #000 !important;
          padding: 6px 8px !important;
          font-size: 13px !important;
          line-height: 1.4 !important;
          vertical-align: top !important;
        }
        .table-container table th {
          background-color: #2d2d2d !important;
          color: white !important;
          font-weight: 600 !important;
          text-align: center !important;
        }
        .table-container table td {
          background-color: white !important;
        }
      `}} />

      {/* Save Changes Banner */}
      {hasEdits && (
        <Card className="p-4 mb-0 bg-yellow-50 border-yellow-200 rounded-none border-x-0 border-t-0">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Badge variant="secondary">
                {Object.keys(edits).length} block(s) modified
              </Badge>
              <span className="text-sm text-muted-foreground">
                Changes are not saved yet
              </span>
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={handleCancelEdits}
                disabled={isSaving}
              >
                <X className="w-4 h-4 mr-2" />
                Cancel
              </Button>
              <Button
                variant="default"
                size="sm"
                onClick={handleSave}
                disabled={isSaving}
              >
                <Save className="w-4 h-4 mr-2" />
                {isSaving ? 'Saving...' : 'Save Changes'}
              </Button>
            </div>
          </div>
        </Card>
      )}

      {/* Controls */}
      <div className="flex items-center justify-between p-4 bg-gray-50 border-b shrink-0">
        <div className="flex items-center gap-2 text-sm text-gray-600">
          <span className="font-medium">BBox Document Renderer</span>
          <span>•</span>
          <span>{currentPageBlocks.length} blocks</span>
        </div>

        <div className="flex items-center gap-4">
          {/* Page navigation */}
          {totalPages > 1 && (
            <div className="flex items-center gap-2">
              <button
                onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                disabled={currentPage === 1}
                className="p-1 rounded hover:bg-gray-200 disabled:opacity-30"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <span className="text-sm min-w-[80px] text-center">
                Page {currentPage} / {totalPages}
              </span>
              <button
                onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                disabled={currentPage === totalPages}
                className="p-1 rounded hover:bg-gray-200 disabled:opacity-30"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          )}

          {/* Zoom controls */}
          <div className="flex items-center gap-2">
            <button
              onClick={() => setScale(s => Math.max(0.5, s - 0.1))}
              disabled={scale <= 0.5}
              className="p-1 rounded hover:bg-gray-200 disabled:opacity-30"
            >
              <ZoomOut className="w-4 h-4" />
            </button>
            <span className="text-sm min-w-[50px] text-center">
              {Math.round(scale * 100)}%
            </span>
            <button
              onClick={() => setScale(s => Math.min(3, s + 0.1))}
              disabled={scale >= 3}
              className="p-1 rounded hover:bg-gray-200 disabled:opacity-30"
            >
              <ZoomIn className="w-4 h-4" />
            </button>
            <button
              onClick={() => setScale(1)}
              className="p-1 rounded hover:bg-gray-200"
            >
              <RotateCw className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Document Canvas */}
      <div ref={containerRef} className="flex-1 overflow-y-auto overflow-x-hidden bg-gray-100 p-4">
        <div className="mx-auto max-w-5xl">
          {/* Page container - stacked layout like Reducto */}
          <div className="bg-white shadow-lg p-8">
            {/* Render each block in linear/stacked layout */}
            {currentPageBlocks.map((block, index) => {
              const blockKey = `block_${allBlocks.indexOf(block)}`
              const currentContent = edits[blockKey] !== undefined ? edits[blockKey] : (block.content || '')
              const globalIndex = allBlocks.indexOf(block)

              return (
                <div
                  key={`${block.type}-${index}`}
                  className={`mb-4 ${edits[blockKey] !== undefined ? 'ring-2 ring-yellow-400' : ''}`}
                  style={{
                    fontSize: block.type === 'Title' ? '18px' :
                             block.type === 'Section Header' ? '15px' :
                             block.type === 'Table' ? '13px' : '13px',
                    fontWeight: block.type === 'Title' ? 'bold' :
                               block.type === 'Section Header' ? '600' : 'normal',
                    lineHeight: '1.5',
                  }}
                >
                  {/* Render content based on type */}
                  {block.type === 'Table' && block.content ? (
                    <div
                      contentEditable
                      suppressContentEditableWarning
                      spellCheck={false}
                      onBlur={(e) => {
                        // Sanitize user input to prevent XSS from pasted content
                        const rawContent = e.currentTarget.innerHTML
                        const sanitizedContent = sanitizeHtml(rawContent)
                        if (sanitizedContent !== block.content) {
                          handleContentEdit(globalIndex, sanitizedContent)
                        }
                      }}
                      dangerouslySetInnerHTML={{ __html: markdownTableToHTML(currentContent) }}
                      className="w-full outline-none focus:ring-2 focus:ring-blue-400 cursor-text table-container"
                    />
                  ) : block.type === 'Figure' ? (
                    block.image_url ? (
                      <img
                        src={block.image_url}
                        alt="Figure"
                        className="w-full object-contain"
                      />
                    ) : (
                      <span className="text-gray-400 text-xs">Figure</span>
                    )
                  ) : (
                    <div
                      contentEditable
                      suppressContentEditableWarning
                      spellCheck={false}
                      onBlur={(e) => {
                        const newContent = e.currentTarget.textContent || ''
                        if (newContent !== block.content) {
                          handleContentEdit(globalIndex, newContent)
                        }
                      }}
                      className="outline-none focus:ring-2 focus:ring-blue-400 cursor-text"
                      style={{ whiteSpace: 'pre-wrap' }}
                    >
                      {currentContent}
                    </div>
                  )}
                </div>
              )
            })}

            {/* Empty page indicator */}
            {currentPageBlocks.length === 0 && (
              <div className="flex items-center justify-center text-gray-400 py-20">
                <p>No content on this page</p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Approve Button - Always visible */}
      <Card className="p-4 mt-4 mx-8 mb-4 bg-green-50 border-green-200">
        <div className="flex items-center justify-between">
          <div className="flex flex-col gap-1">
            <span className="font-semibold text-green-900">
              Ready to save to database?
            </span>
            <span className="text-sm text-green-700">
              This will save all extracted data {hasEdits ? '(including your changes) ' : ''}to the database
            </span>
          </div>
          <Button
            variant="default"
            size="lg"
            onClick={handleApprove}
            disabled={isApproving || isSaving}
            className="bg-green-600 hover:bg-green-700 text-white"
          >
            <CheckCircle className="w-5 h-5 mr-2" />
            {isApproving ? 'Approving...' : 'Approve & Save'}
          </Button>
        </div>
      </Card>
    </div>
  )
}
