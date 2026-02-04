/**
 * Universal HTML Table Parser
 * Handles any HTML table structure with merged cells (colspan/rowspan)
 * Works for timetables, schedules, invoices, reports - any tabular data
 */

import React from 'react'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'

interface ParsedTable {
  headers: string[][]
  rows: string[][]
  cellStyles: CellStyle[][]
}

interface CellStyle {
  colspan?: number
  rowspan?: number
  isHeader?: boolean
  backgroundColor?: string
  alignment?: string
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
 * Detect if content contains HTML table markup
 */
export function isHtmlTable(content: string): boolean {
  // Check both original and decoded content
  const decodedContent = decodeHtmlEntities(content)

  // More lenient HTML tag detection
  const hasHtmlTags = /<\s*(table|tr|td|th)/i.test(content)
  const hasEncodedTags = /&lt;\s*(table|tr|td|th)/i.test(content)

  // Also check for closing tags
  const hasClosingTags = /<\/\s*(table|tr|td|th)\s*>/i.test(content)

  // Debug logging
  console.log('🔍 isHtmlTable check:', {
    hasHtmlTags,
    hasEncodedTags,
    hasClosingTags,
    contentStart: content.substring(0, 100)
  })

  return hasHtmlTags || hasEncodedTags || hasClosingTags
}

/**
 * Fix malformed HTML table structure
 */
function fixMalformedHtml(htmlContent: string): string {
  let fixed = htmlContent

  // Fix missing closing tags that are concatenated without space
  // Example: &lt;/td&gt;&lt;td&gt; becomes &lt;/td&gt;&lt;td&gt;
  fixed = fixed.replace(/&lt;\/td&gt;&lt;(td|th)&gt;/gi, '&lt;/td&gt;&lt;$1&gt;')
  fixed = fixed.replace(/&lt;\/tr&gt;&lt;tr&gt;/gi, '&lt;/tr&gt;&lt;tr&gt;')

  // Fix specific malformed patterns from the example
  // "03-May-1903-May-19" -> "03-May-19</td><td>03-May-19"
  fixed = fixed.replace(/(\d{1,2}-[A-Za-z]{3}-\d{2})(\d{1,2}-[A-Za-z]{3}-\d{2})/g, '$1&lt;/td&gt;&lt;td&gt;$2')

  // "1.00PM 2.15PM10.00AM-11.15AM" -> "1.00PM 2.15PM</td><td>10.00AM-11.15AM"
  fixed = fixed.replace(/(AM|PM)(\d{1,2}\.\d{2}[AP]M)/g, '$1&lt;/td&gt;&lt;td&gt;$2')

  // "BIT324BIT323" -> "BIT324</td><td>BIT323"
  fixed = fixed.replace(/([A-Z]{3}\d{3})([A-Z]{3}\d{3})/g, '$1&lt;/td&gt;&lt;td&gt;$2')

  // "sem6sem6" -> "sem6</td><td>sem6"
  fixed = fixed.replace(/(sem\d)(sem\d)/g, '$1&lt;/td&gt;&lt;td&gt;$2')

  // "G04G04" -> "G04</td><td>G04"
  fixed = fixed.replace(/([A-Z]\d{2})([A-Z]\d{2})(?!\d)/g, '$1&lt;/td&gt;&lt;td&gt;$2')

  // "Small Business Management &amp;Entrepreneurship" -> "Small Business Management &amp; Entrepreneurship"
  fixed = fixed.replace(/&amp;([A-Z])/g, '&amp; $1')

  return fixed
}

/**
 * Alternative parser for severely malformed HTML
 */
export function parseMalformedTable(htmlContent: string): ParsedTable | null {
  // First decode the HTML
  const decoded = decodeHtmlEntities(htmlContent)

  // Try to extract data using regex patterns
  const rows: string[][] = []
  const cellStyles: CellStyle[][] = []

  // Extract header
  const headerMatch = decoded.match(/<tr>(.*?)<\/tr>/is)
  if (headerMatch) {
    const headerCells = headerMatch[1].match(/<th[^>]*>(.*?)<\/th>/gi)
    if (headerCells) {
      const headers = headerCells.map(cell => cell.replace(/<[^>]*>/g, '').trim())
      rows.push(headers)
      cellStyles.push(headers.map(() => ({ isHeader: true })))
    }
  }

  // Extract data rows
  const rowMatches = decoded.match(/<tr>(.*?)<\/tr>/gi)
  if (rowMatches) {
    // Skip first row if it was processed as header
    const startIndex = headerMatch ? 1 : 0

    for (let i = startIndex; i < rowMatches.length; i++) {
      const rowContent = rowMatches[i]

      // Try to extract cells properly
      let cells = rowContent.match(/<t[dh][^>]*>(.*?)<\/t[dh]>/gi)

      if (!cells) {
        // If no proper tags, try to split by known patterns
        const textContent = rowContent.replace(/<[^>]*>/g, '').trim()

        // Skip empty rows
        if (!textContent) continue

        // Try to parse concatenated data
        const patterns = [
          // Date pattern
          /(\d{1,2}-[A-Za-z]{3}-\d{2})/,
          // Time pattern
          /(\d{1,2}\.\d{2}[AP]M(?:-\d{1,2}\.\d{2}[AP]M)?)/,
          // Course code
          /([A-Z]{3}\d{3})/,
          // Course name (more complex)
          /([A-Z][a-zA-Z\s&]+)/,
          // Semester
          /(sem\d)/,
          // Room number
          /([A-Z]\d{2,3})/,
          // Seat number
          /(\d{1,3})/,
          // Name (capitalized words)
          /([A-Z][a-z]+)/
        ]

        cells = []
        let remaining = textContent

        // Apply patterns to extract data
        for (const pattern of patterns) {
          const match = remaining.match(pattern)
          if (match) {
            cells.push(match[1])
            remaining = remaining.replace(match[1], '').trim()
          }
        }
      }

      if (cells && cells.length > 0) {
        const cleanCells = cells.map(cell =>
          cell.replace(/<[^>]*>/g, '').trim()
        ).filter(cell => cell)

        if (cleanCells.length > 0) {
          rows.push(cleanCells)
          cellStyles.push(cleanCells.map(() => ({})))
        }
      }
    }
  }

  if (rows.length === 0) return null

  return {
    headers: rows.slice(0, 1),
    rows: rows.slice(1),
    cellStyles
  }
}

/**
 * Universal parser for any HTML table structure
 */
export function parseHtmlTable(htmlContent: string): ParsedTable | null {
  // Check if we're in browser environment
  if (typeof window === 'undefined' || typeof DOMParser === 'undefined') {
    // Server-side fallback - return null to skip HTML parsing
    return null
  }

  // Decode HTML entities first
  let decodedContent = decodeHtmlEntities(htmlContent)

  // Fix malformed HTML structure
  decodedContent = fixMalformedHtml(decodedContent)

  console.log('🔧 Fixed HTML:', decodedContent.substring(0, 500))

  // Create a temporary DOM element to parse HTML
  const parser = new DOMParser()
  const doc = parser.parseFromString(decodedContent, 'text/html')
  const table = doc.querySelector('table')

  if (!table) {
    // Try the malformed parser as fallback
    console.log('🔧 Using malformed HTML parser as fallback')
    return parseMalformedTable(htmlContent)
  }

  const rows = table.querySelectorAll('tr')
  if (rows.length === 0) return null

  const headers: string[][] = []
  const bodyRows: string[][] = []
  const allCellStyles: CellStyle[][] = []

  // Process each row
  rows.forEach((tr, rowIndex) => {
    const cells = tr.querySelectorAll('td, th')
    const rowData: string[] = []
    const rowStyles: CellStyle[] = []

    cells.forEach((cell, cellIndex) => {
      const textContent = cell.textContent?.trim() || ''
      rowData.push(textContent)

      const style: CellStyle = {
        colspan: cell.getAttribute('colspan') ? parseInt(cell.getAttribute('colspan')!) : 1,
        rowspan: cell.getAttribute('rowspan') ? parseInt(cell.getAttribute('rowspan')!) : 1,
        isHeader: cell.tagName === 'TH',
        backgroundColor: cell.getAttribute('bgcolor'),
        alignment: cell.getAttribute('align') || cell.getAttribute('valign'),
        className: generateUniversalCellStyle(cell, textContent)
      }

      rowStyles.push(style)
    })

    allCellStyles.push(rowStyles)

    // Determine if this is a header row
    const isHeaderRow = Array.from(cells).some(cell => cell.tagName === 'TH') ||
                       rowIndex === 0 || // First row often header
                       hasHeaderCharacteristics(rowData)

    if (isHeaderRow) {
      headers.push(rowData)
    } else {
      bodyRows.push(rowData)
    }
  })

  return {
    headers,
    rows: bodyRows,
    cellStyles: allCellStyles
  }
}

/**
 * Determine if a row has header characteristics
 */
function hasHeaderCharacteristics(rowData: string[]): boolean {
  const headerPatterns = [
    /^[A-Z][a-z]+$/,           // Capitalized words
    /\b(ID|Name|Date|Time|Description|Amount|Total|Status)\b/i,
    /\d{4}-\d{2}-\d{2}/,       // Date format
    /^\w+$/                    // Single words
  ]

  const headerLikeCells = rowData.filter(cell =>
    headerPatterns.some(pattern => pattern.test(cell))
  )

  return headerLikeCells.length >= Math.min(2, rowData.length)
}

/**
 * Generate universal CSS classes based on cell content and attributes
 */
function generateUniversalCellStyle(cell: HTMLTableCellElement, content: string): string {
  let classes = 'border border-border text-sm '

  // Header styling
  if (cell.tagName === 'TH') {
    classes += 'font-semibold bg-muted/50 '
  }
  // Numeric content
  else if (/^\d+(\.\d+)?$/.test(content) || /^\$?\d[\d,]*\.?\d*$/.test(content)) {
    classes += 'text-right font-medium '
  }
  // Date/time content
  else if (/\d{4}-\d{2}-\d{2}|\d{1,2}\/\d{1,2}\/\d{4}|\d{1,2}:\d{2}/.test(content)) {
    classes += 'text-center '
  }
  // Status indicators
  else if (/^(Active|Inactive|Pending|Complete|Open|Closed)$/i.test(content)) {
    classes += 'text-center font-medium '
  }
  // Empty cells
  else if (!content || content === '-' || content.toLowerCase() === 'null') {
    classes += 'text-muted-foreground/50 '
  }

  // Alignment based on HTML attributes
  if (cell.getAttribute('align')) {
    classes += `text-${cell.getAttribute('align')} `
  }

  // Vertical alignment
  if (cell.getAttribute('valign')) {
    classes += `align-${cell.getAttribute('valign')} `
  } else if (content.length > 20) {
    classes += 'align-top '
  } else {
    classes += 'align-middle '
  }

  return classes
}

/**
 * Universal HTML Table Renderer with proper merged cell handling
 */
export function UniversalHtmlTableRenderer({ content, onEdit, edits }: {
  content: string
  onEdit?: (cellKey: string, newValue: string) => void
  edits?: Record<string, string>
}) {
  // Use React.useEffect to ensure client-side only execution
  const [parsedTable, setParsedTable] = React.useState<ParsedTable | null>(null)
  const [isClient, setIsClient] = React.useState(false)

  console.log('🏗️ UniversalHtmlTableRenderer:', { hasOnEdit: !!onEdit, editsCount: Object.keys(edits || {}).length })

  React.useEffect(() => {
    setIsClient(true)
    const result = parseHtmlTable(content)
    setParsedTable(result)
  }, [content])

  // Server-side render fallback
  if (!isClient) {
    return (
      <div className="p-4 bg-muted/30 rounded-lg">
        <pre className="text-xs font-mono whitespace-pre-wrap">{content}</pre>
      </div>
    )
  }

  // Client-side render
  if (!parsedTable) {
    // Fallback to preformatted text
    return (
      <div className="p-4 bg-muted/30 rounded-lg">
        <pre className="text-xs font-mono whitespace-pre-wrap">{content}</pre>
      </div>
    )
  }

  const { headers, rows, cellStyles } = parsedTable

  // Create a grid to track occupied cells for rowspan/colspan
  const occupiedCells = new Set<string>()

  const renderCell = (
    content: string,
    rowIndex: number,
    cellIndex: number,
    style: CellStyle,
    isHeader: boolean = false
  ) => {
    const cellKey = `${rowIndex}-${cellIndex}`

    // Skip if cell is already occupied by a rowspan/colspan
    if (occupiedCells.has(cellKey)) {
      return null
    }

    // Mark this cell and any cells it spans as occupied
    for (let r = rowIndex; r < rowIndex + (style.rowspan || 1); r++) {
      for (let c = cellIndex; c < cellIndex + (style.colspan || 1); c++) {
        occupiedCells.add(`${r}-${c}`)
      }
    }

    const CellComponent = isHeader ? TableHead : TableCell
    const prefixedCellKey = `table_${cellKey}`
    const currentValue = edits?.[prefixedCellKey] !== undefined ? edits[prefixedCellKey] : content

    // Debug all cells
    console.log('🔍 Processing cell:', {
      cellKey,
      content,
      isHeader,
      hasOnEdit: !!onEdit,
      canEdit: !isHeader && !!onEdit,
      rowIndex,
      cellIndex
    })

    // Allow editing for ALL cells (temporarily for testing)
    if (onEdit) {
      console.log('🔧 Editable cell:', { cellKey, isHeader, hasOnEdit: !!onEdit, currentValue })

      // Create an editable cell with contenteditable
      return (
        <CellComponent
          key={cellKey}
          colSpan={style.colspan}
          rowSpan={style.rowspan}
          className={`${style.className} cursor-text bg-blue-50 hover:bg-blue-100`}
          style={{
            wordBreak: 'break-word',
            backgroundColor: style.backgroundColor ?
              (style.backgroundColor.startsWith('#') ? style.backgroundColor :
               convertNamedColor(style.backgroundColor)) : undefined,
          }}
          contentEditable={true}
          suppressContentEditableWarning={true}
          onFocus={() => console.log('📝 Cell focused:', cellKey)}
          onInput={(e) => {
            const newValue = e.currentTarget.textContent || ''
            console.log('✏️ Cell edited:', cellKey, 'to:', newValue)
            // Debounce the edit to avoid too many updates
            setTimeout(() => {
              if (newValue !== currentValue) {
                onEdit(cellKey, newValue)
              }
            }, 500)
          }}
          onBlur={(e) => {
            const newValue = e.currentTarget.textContent || ''
            console.log('💾 Cell saved:', cellKey, 'to:', newValue)
            if (newValue !== currentValue) {
              onEdit(cellKey, newValue)
            }
          }}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault()
              e.currentTarget.blur()
            }
            if (e.key === 'Escape') {
              e.currentTarget.textContent = currentValue
              e.currentTarget.blur()
            }
          }}
          title="Click to edit (Enter to save, Esc to cancel)"
        >
          {currentValue || '-'}
        </CellComponent>
      )
    }

    return (
      <CellComponent
        key={cellKey}
        colSpan={style.colspan}
        rowSpan={style.rowspan}
        className={`${style.className || ''}`}
        style={{
          wordBreak: 'break-word',
          backgroundColor: style.backgroundColor ?
            (style.backgroundColor.startsWith('#') ? style.backgroundColor :
             convertNamedColor(style.backgroundColor)) : undefined,
        }}
      >
        {content || '-'}
      </CellComponent>
    )
  }

  // Convert named colors to hex
  const convertNamedColor = (color: string): string => {
    const colorMap: Record<string, string> = {
      'e6e6fa': '#e6e6fa',  // lavender
      'white': '#ffffff',
      'black': '#000000',
      'gray': '#808080',
      'silver': '#c0c0c0',
      'red': '#ff0000',
      'blue': '#0000ff',
      'green': '#008000',
      'yellow': '#ffff00',
      'orange': '#ffa500',
      'purple': '#800080'
    }
    return colorMap[color.toLowerCase()] || color
  }

  return (
    <div className="overflow-x-auto">
      <Table className="border-collapse border border-border">
        {/* Render headers */}
        {headers.map((headerRow, headerRowIndex) => (
          <TableHeader key={headerRowIndex}>
            <TableRow>
              {headerRow.map((header, cellIndex) => {
                const style = cellStyles[headerRowIndex]?.[cellIndex]
                return renderCell(
                  header,
                  headerRowIndex,
                  cellIndex,
                  style || {},
                  true
                )
              })}
            </TableRow>
          </TableHeader>
        ))}

        {/* Render body rows */}
        <TableBody>
          {rows.map((row, rowIndex) => {
            const actualRowIndex = headers.length + rowIndex
            return (
              <TableRow key={rowIndex}>
                {row.map((cell, cellIndex) => {
                  const style = cellStyles[actualRowIndex]?.[cellIndex]
                  return renderCell(
                    cell,
                    actualRowIndex,
                    cellIndex,
                    style || {},
                    false
                  )
                })}
              </TableRow>
            )
          })}
        </TableBody>
      </Table>
    </div>
  )
}