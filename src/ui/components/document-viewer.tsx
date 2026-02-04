"use client"

import { Card } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"

interface Block {
    type: string
    content: string
    bbox?: {
        left: number
        top: number
        width: number
        height: number
        page: number
    }
    confidence?: string
}

interface DocumentViewerProps {
    content: string
    blocks?: Block[]
    title?: string
}

/**
 * Universal Document Viewer
 *
 * Displays extracted document content in a readable format,
 * preserving the original structure and layout from the OCR extraction.
 *
 * This component is completely dynamic and works with ANY document type.
 */
export function DocumentViewer({ content, blocks, title }: DocumentViewerProps) {
    // Split content into sections based on blank lines
    const sections = content.split('\n\n').filter(s => s.trim())

    // Detect if this is a structured form (has numbered fields like "1 Field:", "2 Field:")
    const isStructuredForm = /^\d+\s+[\w\s]+:/.test(content)

    return (
        <Card className="p-8">
            {title && (
                <div className="mb-6 pb-4 border-b">
                    <h2 className="text-2xl font-bold">{title}</h2>
                </div>
            )}

            <div className="space-y-6">
                {sections.map((section, idx) => (
                    <DocumentSection key={idx} content={section} index={idx} />
                ))}
            </div>

            {/* Show blocks info if available for debugging */}
            {blocks && blocks.length > 0 && (
                <details className="mt-8 p-4 bg-muted rounded-lg text-xs">
                    <summary className="cursor-pointer font-semibold mb-2">
                        Structure Info ({blocks.length} blocks)
                    </summary>
                    <div className="space-y-2 max-h-60 overflow-y-auto">
                        {blocks.map((block, idx) => (
                            <div key={idx} className="flex items-start gap-2">
                                <Badge variant="outline" className="shrink-0">
                                    {block.type}
                                </Badge>
                                <span className="text-muted-foreground">
                                    {block.content.substring(0, 100)}...
                                </span>
                            </div>
                        ))}
                    </div>
                </details>
            )}
        </Card>
    )
}

interface DocumentSectionProps {
    content: string
    index: number
}

function DocumentSection({ content, index }: DocumentSectionProps) {
    const lines = content.split('\n').filter(l => l.trim())

    // Detect section type
    const firstLine = lines[0]
    const isTitle = firstLine === firstLine.toUpperCase() && firstLine.length > 10 && !firstLine.includes(':')
    const isHeader = firstLine.startsWith('#')

    // Check if this is a multi-field section (has multiple "Field: Value" pairs)
    const hasMultipleFields = lines.filter(l => l.includes(':')).length > 1

    if (isTitle) {
        return (
            <div className="text-center py-4">
                <h1 className="text-2xl font-bold text-primary">
                    {firstLine.replace(/^#+\s*/, '')}
                </h1>
                {lines.slice(1).map((line, i) => (
                    <p key={i} className="text-lg font-semibold text-muted-foreground mt-1">
                        {line.replace(/^#+\s*/, '')}
                    </p>
                ))}
            </div>
        )
    }

    if (hasMultipleFields) {
        return (
            <div className="space-y-3 bg-muted/30 p-4 rounded-lg border border-border">
                {lines.map((line, i) => (
                    <FieldLine key={i} line={line} />
                ))}
            </div>
        )
    }

    // Single field or text block
    return (
        <div className="space-y-2">
            {lines.map((line, i) => (
                <FieldLine key={i} line={line} />
            ))}
        </div>
    )
}

interface FieldLineProps {
    line: string
}

function FieldLine({ line }: FieldLineProps) {
    // Check if line has field:value pattern
    const colonIndex = line.indexOf(':')

    if (colonIndex === -1) {
        // Plain text line
        return (
            <p className="text-base leading-relaxed">
                {line}
            </p>
        )
    }

    const label = line.substring(0, colonIndex + 1).trim()
    const value = line.substring(colonIndex + 1).trim()

    // Check if value is empty
    const isEmpty = !value || value === '<empty>' || value.toLowerCase() === 'null'

    // Detect if label has number prefix (structured form field)
    const hasNumberPrefix = /^\d+\s/.test(label)

    return (
        <div className="flex flex-col sm:flex-row sm:items-start gap-2 py-2 border-b border-border/50 last:border-0">
            <div className={`font-semibold min-w-[200px] ${hasNumberPrefix ? 'text-primary' : 'text-foreground'}`}>
                {label}
            </div>
            <div className={`flex-1 ${isEmpty ? 'text-muted-foreground italic' : 'font-medium'}`}>
                {value || '<empty>'}
            </div>
        </div>
    )
}
