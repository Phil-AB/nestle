/**
 * Universal Table Renderer for Document Extraction
 *
 * Handles complex table structures including:
 * - Merged cells (rowspan and colspan)
 * - HTML tables with proper parsing
 * - Text-based tables (tab-separated, space-aligned)
 * - Dynamic table detection from content
 * - Preserves original table structure
 */

import React from 'react'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { Card } from '@/components/ui/card'
import { UniversalHtmlTableRenderer, isHtmlTable } from './html-table-parser'

interface TableData {
  headers: string[][]
  rows: string[][]
  cellStyles?: CellStyle[][]
}

interface CellStyle {
  colspan?: number
  rowspan?: number
  isHeader?: boolean
  className?: string
}

interface TableRendererProps {
  content: string
  confidence?: string
  granularConfidence?: {
    extract_confidence?: number | null
    parse_confidence?: number | null
  }
  className?: string
}

/**
 * Decode HTML entities in content
 */
function decodeHtmlEntities(text: string): string {
  if (typeof window === 'undefined') return text
  const textArea = document.createElement('textarea')
  textArea.innerHTML = text
  return textArea.value
}

/**
 * Detects if content contains a table structure
 */
export function isTableContent(content: string): boolean {
  // Try to decode HTML entities first
  let decodedContent = content
  try {
    if (typeof window !== 'undefined') {
      decodedContent = decodeHtmlEntities(content)
    }
  } catch (e) {
    // If decoding fails, use original content
  }

  // First check for HTML table tags (most reliable)
  const hasHtmlTags = /<\s*(table|tr|td|th)\s*>/i.test(content) ||
                      /<\s*(table|tr|td|th)\s*>/i.test(decodedContent) ||
                      /&lt;\s*(table|tr|td|th)\s*&gt;/i.test(content)

  if (hasHtmlTags) return true

  // Check for Markdown table format
  const lines = content.split('\n').filter(line => line.trim())
  if (lines.length >= 2) {
    // Check for | separators (Markdown tables)
    const hasMarkdownTable = lines.some(line => line.includes('|') && line.split('|').length > 2)
    if (hasMarkdownTable) return true
  }

  // For non-HTML content, be more strict about table detection
  if (lines.length < 2) return false

  // Check for at least 2 rows with multiple columns
  let rowsWithMultipleColumns = 0

  for (const line of lines) {
    // Skip title lines (all caps or very short)
    if (line.length < 5 || line === line.toUpperCase()) continue

    // Count potential columns by looking for separators
    const hasTabs = line.includes('\t')
    const hasMultipleSpaces = /\s{3,}/.test(line)
    const hasPipes = /\s*\|\s*/.test(line)

    // Count words - single words are not table rows
    const wordCount = line.trim().split(/\s+/).length

    if (hasTabs || hasMultipleSpaces || hasPipes) {
      rowsWithMultipleColumns++
    } else if (wordCount >= 4) {
      // Might be a space-separated table
      rowsWithMultipleColumns++
    }
  }

  // Need at least 2 rows with multiple columns to be considered a table
  return rowsWithMultipleColumns >= 2
}

/**
 * Parse content into table structure
 * Handles various formats:
 * - HTML tables (with proper parsing)
 * - Tab-separated values
 * - Space-aligned columns
 * - Markdown-style tables
 */
function parseTableContent(content: string): TableData | null {
  // First check if it's an HTML table
  if (isHtmlTable(content)) {
    // For HTML tables, we'll use the dedicated renderer
    return null // Let UniversalHtmlTableRenderer handle it
  }

  // Check for Markdown table format
  const isMarkdownTable = /^\|.*\|$/.test(content.trim().split('\n')[0] || '')

  if (isMarkdownTable) {
    // Parse Markdown table
    const lines = content.split('\n').filter(line => line.trim())
    if (lines.length < 2) return null

    // Skip separator line (e.g., |-|-|-|)
    const separatorLineIndex = lines.findIndex(line => /^[\s\|:-]+$/.test(line))

    let headers: string[] = []
    let rows: string[][] = []

    if (separatorLineIndex > 0) {
      // Parse headers (before separator)
      const headerLine = lines[0]
      headers = headerLine.split('|')
        .map(cell => cell.trim())
        .filter(cell => cell)

      // Parse rows (after separator)
      rows = lines.slice(separatorLineIndex + 1).map(line =>
        line.split('|')
          .map(cell => cell.trim())
          .filter(cell => cell)
      )
    } else {
      // No separator line, treat all as rows
      rows = lines.map(line =>
        line.split('|')
          .map(cell => cell.trim())
          .filter(cell => cell)
      )
    }

    if (rows.length === 0) return null

    return {
      headers: headers.length > 0 ? [headers] : [],
      rows,
      cellStyles: []
    }
  }

  // Try tab-separated or space-aligned table
  const lines = content.split('\n').filter(line => line.trim())
  if (lines.length < 2) return null

  // Determine separator
  const separator = detectSeparator(lines)
  if (!separator) return null

  try {
    const headers = parseTableRow(lines[0], separator)
    const rows = lines.slice(1).map(line => parseTableRow(line, separator))

    // Detect merged cells by analyzing cell content patterns
    const cellStyles = detectMergedCells(headers, rows)

    return {
      headers: [headers],
      rows,
      cellStyles
    }
  } catch (error) {
    console.error('Failed to parse table content:', error)
    return null
  }
}

/**
 * Parse HTML table content
 */
function parseHtmlTable(content: string): TableData | null {
  const parser = new DOMParser()
  const doc = parser.parseFromString(content, 'text/html')
  const table = doc.querySelector('table')

  if (!table) return null

  const headers: string[][] = []
  const rows: string[][] = []
  const cellStyles: CellStyle[][] = []

  // Parse headers
  const headerRows = table.querySelectorAll('thead tr')
  headerRows.forEach(tr => {
    const headerRow: string[] = []
    const headerStyles: CellStyle[] = []

    tr.querySelectorAll('th, td').forEach(cell => {
      headerRow.push(cell.textContent?.trim() || '')
      const style: CellStyle = {
        colspan: cell.getAttribute('colspan') ? parseInt(cell.getAttribute('colspan')!) : undefined,
        rowspan: cell.getAttribute('rowspan') ? parseInt(cell.getAttribute('rowspan')!) : undefined,
        isHeader: true
      }
      headerStyles.push(style)
    })

    headers.push(headerRow)
    cellStyles.push(headerStyles)
  })

  // Parse body rows
  const bodyRows = table.querySelectorAll('tbody tr, tr')
  bodyRows.forEach(tr => {
    const isHeaderRow = Array.from(tr.children).some(child => child.tagName === 'TH')
    if (isHeaderRow) return // Skip header rows already processed

    const row: string[] = []
    const rowStyles: CellStyle[] = []

    tr.querySelectorAll('td, th').forEach(cell => {
      row.push(cell.textContent?.trim() || '')
      const style: CellStyle = {
        colspan: cell.getAttribute('colspan') ? parseInt(cell.getAttribute('colspan')!) : undefined,
        rowspan: cell.getAttribute('rowspan') ? parseInt(cell.getAttribute('rowspan')!) : undefined,
        isHeader: cell.tagName === 'TH'
      }
      rowStyles.push(style)
    })

    if (row.length > 0) {
      rows.push(row)
      cellStyles.push(rowStyles)
    }
  })

  return { headers, rows, cellStyles }
}

/**
 * Detect the separator used in the table
 */
function detectSeparator(lines: string[]): string | null {
  const firstLine = lines[0]

  // Check for tabs
  if (firstLine.includes('\t')) return '\t'

  // Check for multiple spaces (aligned columns)
  const spaceGroups = firstLine.match(/\s{2,}/g)
  if (spaceGroups && spaceGroups.length > 1) return /\s{2,}/

  // Check for pipe separators (Markdown)
  if (firstLine.includes('|')) return /\s*\|\s*/

  return null
}

/**
 * Parse a single table row
 */
function parseTableRow(line: string, separator: RegExp | string): string[] {
  if (typeof separator === 'string') {
    return line.split(separator).map(cell => cell.trim()).filter(cell => cell)
  } else {
    return line.split(separator).map(cell => cell.trim()).filter(cell => cell)
  }
}

/**
 * Detect merged cells by analyzing patterns in the data
 */
function detectMergedCells(headers: string[], rows: string[][]): CellStyle[][] {
  const allRows = [headers, ...rows]
  const cellStyles: CellStyle[][] = []

  allRows.forEach((row, rowIndex) => {
    const rowStyles: CellStyle[] = []
    row.forEach((cell, colIndex) => {
      const style: CellStyle = {}

      // Check for empty cells that might indicate merging
      if (!cell || cell.trim() === '') {
        // Look up to find a non-empty cell to merge with
        for (let r = rowIndex - 1; r >= 0; r--) {
          if (allRows[r][colIndex] && allRows[r][colIndex].trim()) {
            style.rowspan = rowIndex - r + 1
            break
          }
        }
      }

      // Check for repetitive content (common in merged scenarios)
      if (rowIndex > 0 && cell === allRows[rowIndex - 1][colIndex]) {
        style.rowspan = (rowStyles[colIndex - 1]?.rowspan || 1) + 1
      }

      rowStyles.push(style)
    })
    cellStyles.push(rowStyles)
  })

  return cellStyles
}

/**
 * Get confidence badge component
 */
function getConfidenceBadge(
  confidence?: string,
  granularConfidence?: {
    extract_confidence?: number | null
    parse_confidence?: number | null
  }
) {
  if (!confidence && !granularConfidence) return null

  const confidenceScore = granularConfidence?.parse_confidence ?? granularConfidence?.extract_confidence
  const percentage = confidenceScore ? Math.round(confidenceScore * 100) : null

  let badgeClasses = "text-xs font-medium"

  if (percentage !== null) {
    if (percentage >= 90) {
      badgeClasses += " bg-green-100 text-green-800 border-green-300"
    } else if (percentage >= 70) {
      badgeClasses += " bg-yellow-100 text-yellow-800 border-yellow-300"
    } else {
      badgeClasses += " bg-red-100 text-red-800 border-red-300"
    }
  }

  const displayText = percentage !== null ? `${percentage}%` : (confidence || 'unknown')

  return (
    <Badge variant="outline" className={badgeClasses}>
      {displayText}
    </Badge>
  )
}

/**
 * Main Table Renderer Component
 */
export function TableRenderer({
  content,
  confidence,
  granularConfidence,
  className = "",
  onEdit,
  edits
}: TableRendererProps & {
  onEdit?: (cellKey: string, newValue: string) => void
  edits?: Record<string, string>
}) {
  const confidenceBadge = getConfidenceBadge(confidence, granularConfidence)

  // Debug logging
  console.log('🏷️ TableRenderer received content:', {
    contentLength: content.length,
    contentPreview: content.substring(0, 200),
    hasHtmlTags: /<[^>]+>/.test(content),
    hasEncodedTags: /&lt;[^&]+&gt;/.test(content),
    isHtmlTable: isHtmlTable(content),
    isTableContent: isTableContent(content)
  })

  // Check if it's an HTML table first
  if (isHtmlTable(content)) {
    console.log('✅ Detected HTML table, rendering with UniversalHtmlTableRenderer')
    return (
      <Card className={`p-4 ${className}`}>
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <Badge variant="outline" className="text-xs bg-green-50 text-green-700 border-green-300">
              HTML Table
            </Badge>
            {confidenceBadge}
          </div>
          <UniversalHtmlTableRenderer content={content} onEdit={onEdit} edits={edits} />
        </div>
      </Card>
    )
  }

  const tableData = parseTableContent(content)

  if (!tableData) {
    // Fallback to preformatted text if parsing fails
    return (
      <Card className={`p-4 ${className}`}>
        <pre className="text-sm font-mono whitespace-pre-wrap">{content}</pre>
        {confidenceBadge && (
          <div className="mt-2 flex justify-end">
            {confidenceBadge}
          </div>
        )}
      </Card>
    )
  }

  const { headers, rows, cellStyles } = tableData

  return (
    <Card className={`p-4 overflow-x-auto ${className}`}>
      <div className="space-y-4 overflow-x-auto">
        <Table className="border-collapse min-w-full">
          <TableHeader>
            {headers.map((headerRow, headerRowIndex) => (
              <TableRow key={headerRowIndex}>
                {headerRow.map((header, cellIndex) => {
                  const cellStyle = cellStyles?.[headerRowIndex]?.[cellIndex]
                  return (
                    <TableHead
                      key={cellIndex}
                      colSpan={cellStyle?.colspan}
                      rowSpan={cellStyle?.rowspan}
                      className={`font-semibold border border-border bg-muted/50 ${cellStyle?.className || ''}`}
                    >
                      {header}
                    </TableHead>
                  )
                })}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {rows.map((row, rowIndex) => (
              <TableRow key={rowIndex}>
                {row.map((cell, cellIndex) => {
                  const actualRowIndex = headers.length + rowIndex
                  const cellStyle = cellStyles?.[actualRowIndex]?.[cellIndex]

                  const cellKey = `md-${rowIndex}-${cellIndex}`
                  const prefixedCellKey = `table_${cellKey}`
                  const currentValue = edits?.[prefixedCellKey] !== undefined ? edits[prefixedCellKey] : cell

                  return (
                    <TableCell
                      key={cellIndex}
                      colSpan={cellStyle?.colspan}
                      rowSpan={cellStyle?.rowspan}
                      className={`border border-border ${cellStyle?.isHeader ? 'font-semibold bg-muted/30' : ''} ${cellStyle?.className || ''} ${!cellStyle?.isHeader && onEdit ? 'cursor-text bg-blue-50 hover:bg-blue-100' : ''}`}
                      style={{wordBreak: 'break-word'}}
                      contentEditable={!cellStyle?.isHeader && !!onEdit}
                      suppressContentEditableWarning={true}
                      onInput={(e) => {
                        if (!cellStyle?.isHeader && onEdit) {
                          const newValue = e.currentTarget.textContent || ''
                          console.log('✏️ Markdown cell edited:', cellKey, 'to:', newValue)
                          setTimeout(() => {
                            if (newValue !== currentValue) {
                              onEdit(cellKey, newValue)
                            }
                          }, 500)
                        }
                      }}
                      onBlur={(e) => {
                        if (!cellStyle?.isHeader && onEdit) {
                          const newValue = e.currentTarget.textContent || ''
                          console.log('💾 Markdown cell saved:', cellKey, 'to:', newValue)
                          if (newValue !== currentValue) {
                            onEdit(cellKey, newValue)
                          }
                        }
                      }}
                      title={!cellStyle?.isHeader && onEdit ? "Click to edit" : undefined}
                    >
                      {currentValue}
                    </TableCell>
                  )
                })}
              </TableRow>
            ))}
          </TableBody>
        </Table>

        {confidenceBadge && (
          <div className="flex justify-end">
            {confidenceBadge}
          </div>
        )}
      </div>
    </Card>
  )
}

/**
 * Enhanced Table Detection for Complex Layouts
 * Specifically handles exam timetables and similar complex structures
 */
export function detectComplexTable(content: string): boolean {
  const complexPatterns = [
    // Time-based patterns (like timetables)
    /\d{1,2}:\d{2}\s*(AM|PM|am|pm)?/,
    // Day patterns
    /(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)/i,
    // Subject/Course patterns
    /[A-Z]{2,4}\s*\d{3,4}/,
    // Room patterns
    /Room\s+\w+/i,
    // Instructor patterns
    /(Prof|Dr|Mr|Mrs|Ms)\.\s+\w+/i
  ]

  const hasComplexElements = complexPatterns.some(pattern => pattern.test(content))
  const hasGridStructure = isTableContent(content)

  return hasComplexElements && hasGridStructure
}