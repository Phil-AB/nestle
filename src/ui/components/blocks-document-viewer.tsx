"use client"

import React, { useState } from "react"
import { ContentBlock, apiClient } from "@/lib/api-client"
import { Card } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Save, X, Plus, CheckCircle } from "lucide-react"
import { useToast } from "@/hooks/use-toast"
import { TableRenderer, isTableContent, detectComplexTable } from "./table-renderer"

interface BlocksDocumentViewerProps {
    blocks: ContentBlock[]
    showEmpty?: boolean
    documentId?: string
    onSave?: (edits: Record<string, string>) => Promise<void>
    onApprove?: (allData: Record<string, any>) => Promise<void>
}

/**
 * Universal Blocks-Based Document Viewer
 *
 * Displays document by rendering ALL content blocks (Title, Text, Key Value) in order.
 * This preserves the original document structure exactly as extracted by Reducto.
 *
 * Features:
 * - Shows confidence levels for each field
 * - Inline editing for all fields
 * - Tracks and saves changes
 *
 * Works with ANY document type - completely dynamic.
 */
export function BlocksDocumentViewer({ blocks, showEmpty = true, documentId, onSave, onApprove }: BlocksDocumentViewerProps) {
    const [edits, setEdits] = useState<Record<string, string>>({})
    const [newFields, setNewFields] = useState<Record<number, Array<{ label: string; value: string }>>>({})
    const [isSaving, setIsSaving] = useState(false)
    const [isApproving, setIsApproving] = useState(false)
    const { toast } = useToast()

    // Debug logging
    React.useEffect(() => {
        if (blocks && blocks.length > 0) {
            console.log('📄 All blocks:', blocks.map((b, i) => ({
                index: i,
                type: b.type,
                content: b.content ? b.content.substring(0, 200) : '[No content]',
                hasHtmlTags: b.content ? /<[^>]+>/.test(b.content) : false,
                fullContent: b.content || null
            })))
        }
    }, [blocks])

    if (!blocks || blocks.length === 0) {
        return (
            <Card className="p-12 text-center">
                <p className="text-muted-foreground">No content blocks available</p>
            </Card>
        )
    }

    const hasEdits = Object.keys(edits).length > 0 || Object.keys(newFields).length > 0

    const handleFieldEdit = (fieldKey: string, newValue: string) => {
        setEdits(prev => ({
            ...prev,
            [fieldKey]: newValue
        }))
    }

    // Enhanced edit handler for table cells
    const handleTableCellEdit = (cellKey: string, newValue: string) => {
        // Prefix table cell edits with table_ to avoid conflicts
        setEdits(prev => ({
            ...prev,
            [`table_${cellKey}`]: newValue
        }))
    }

    const handleAddField = (blockIdx: number, label: string, value: string) => {
        setNewFields(prev => ({
            ...prev,
            [blockIdx]: [...(prev[blockIdx] || []), { label, value }]
        }))
    }

    const handleRemoveNewField = (blockIdx: number, fieldIdx: number) => {
        setNewFields(prev => {
            const blockFields = prev[blockIdx] || []
            const updated = blockFields.filter((_, idx) => idx !== fieldIdx)
            if (updated.length === 0) {
                const { [blockIdx]: _, ...rest } = prev
                return rest
            }
            return { ...prev, [blockIdx]: updated }
        })
    }

    const handleSave = async () => {
        setIsSaving(true)
        try {
            // Merge edits and new fields into a single object
            const allChanges = { ...edits }

            // Add new fields to changes
            Object.entries(newFields).forEach(([blockIdx, fields]) => {
                fields.forEach((field, idx) => {
                    const fieldKey = `new_${blockIdx}_${idx}_${field.label}`
                    allChanges[fieldKey] = field.value
                })
            })

            // Use custom onSave if provided, otherwise use API client
            if (onSave) {
                await onSave(allChanges)
            } else if (documentId) {
                await apiClient.updateDocumentFields(documentId, allChanges, {
                    updated_by: "user",
                    update_reason: "manual_correction"
                })
            }

            setEdits({}) // Clear edits after successful save
            setNewFields({}) // Clear new fields after successful save

            toast({
                title: "Changes saved",
                description: `Successfully updated ${Object.keys(allChanges).length} field(s)`,
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

    const handleCancelEdits = () => {
        setEdits({})
        setNewFields({})
    }

    const handleApprove = async () => {
        setIsApproving(true)
        try {
            // Collect all data from blocks (original + edits)
            const allData: Record<string, any> = {
                blocks: [],
                fields: {},
                metadata: {
                    document_id: documentId,
                    approved_at: new Date().toISOString(),
                    total_blocks: blocks.length
                }
            }

            // Process each block and collect content
            blocks.forEach((block, idx) => {
                const blockData: any = {
                    type: block.type,
                    content: block.content,
                    confidence: block.confidence,
                    granular_confidence: block.granular_confidence,
                    bbox: block.bbox,
                    page: block.bbox?.page
                }

                // Apply edits if any exist for this block
                const blockKeys = Object.keys(edits).filter(key => key.includes(`_${idx}_`))
                if (blockKeys.length > 0) {
                    blockData.edits = {}
                    blockKeys.forEach(key => {
                        blockData.edits[key] = edits[key]
                    })
                }

                // Include new fields for this block
                if (newFields[idx]) {
                    blockData.new_fields = newFields[idx]
                }

                allData.blocks.push(blockData)
            })

            // Use custom onApprove if provided, otherwise use API client
            if (onApprove) {
                await onApprove(allData)
            } else if (documentId) {
                // Default: save to database via API client
                await apiClient.approveDocument(documentId, allData)
            }

            // Clear edits after successful approval
            setEdits({})
            setNewFields({})

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

    return (
        <>
            {hasEdits && (
                <Card className="p-4 mb-4 bg-yellow-50 border-yellow-200">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                            <Badge variant="secondary">
                                {Object.keys(edits).length + Object.values(newFields).flat().length} field(s) modified
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

            <Card className="p-8">
                <div className="space-y-4">
                    {blocks.map((block, idx) => (
                        <BlockRenderer
                            key={idx}
                            blockIdx={idx}
                            block={block}
                            showEmpty={showEmpty}
                            edits={edits}
                            newFields={newFields[idx] || []}
                            onFieldEdit={handleFieldEdit}
                            onTableCellEdit={handleTableCellEdit}
                            onAddField={handleAddField}
                            onRemoveNewField={handleRemoveNewField}
                        />
                    ))}
                </div>
            </Card>

            {/* Approve Button - Always visible */}
            <Card className="p-4 mt-4 bg-green-50 border-green-200">
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
        </>
    )
}

/**
 * Editable text block component for titles, headers, and standalone text
 */
function EditableTextBlock({
    fieldKey,
    value,
    onEdit,
    confidenceBadge,
    className = "",
    textClassName = ""
}: {
    fieldKey: string
    value: string
    onEdit: (fieldKey: string, newValue: string) => void
    confidenceBadge?: React.ReactElement | null
    className?: string
    textClassName?: string
}) {
    const [isEditing, setIsEditing] = useState(false)
    const [editValue, setEditValue] = useState(value)

    const handleSave = () => {
        if (editValue !== value) {
            onEdit(fieldKey, editValue)
        }
        setIsEditing(false)
    }

    const handleCancel = () => {
        setEditValue(value)
        setIsEditing(false)
    }

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter') {
            handleSave()
        } else if (e.key === 'Escape') {
            handleCancel()
        }
    }

    return (
        <div className={`${className}`}>
            <div className="flex items-start gap-3">
                {isEditing ? (
                    <input
                        type="text"
                        value={editValue}
                        onChange={(e) => setEditValue(e.target.value)}
                        onKeyDown={handleKeyDown}
                        onBlur={handleSave}
                        autoFocus
                        className={`${textClassName} flex-1 px-2 py-1 border border-primary rounded focus:outline-none focus:ring-2 focus:ring-primary bg-background`}
                        style={{wordBreak: 'break-word'}}
                    />
                ) : (
                    <span
                        onClick={() => setIsEditing(true)}
                        className={`${textClassName} cursor-pointer hover:bg-muted/50 px-2 py-1 rounded transition-colors flex-1`}
                        style={{wordBreak: 'break-word', whiteSpace: 'pre-wrap'}}
                    >
                        {value}
                    </span>
                )}
                {confidenceBadge}
            </div>
        </div>
    )
}

/**
 * Get confidence badge component - shared helper function
 */
function getConfidenceBadge(
    confidence?: string,
    granularConfidence?: {
        extract_confidence?: number | null
        parse_confidence?: number | null
    }
) {
    if (!confidence && !granularConfidence) return null

    // Calculate percentage from granular confidence (prefer parse_confidence)
    const confidenceScore = granularConfidence?.parse_confidence ?? granularConfidence?.extract_confidence
    const percentage = confidenceScore ? Math.round(confidenceScore * 100) : null

    // Use custom colors with proper contrast for readability
    let badgeClasses = "text-xs font-medium"

    // If we have a percentage, use percentage-based thresholds
    if (percentage !== null) {
        if (percentage >= 90) {
            badgeClasses += " bg-green-100 text-green-800 border-green-300"
        } else if (percentage >= 70) {
            badgeClasses += " bg-yellow-100 text-yellow-800 border-yellow-300"
        } else {
            badgeClasses += " bg-red-100 text-red-800 border-red-300"
        }
    } else {
        // Fall back to confidence string if no percentage
        if (confidence === 'high') {
            badgeClasses += " bg-green-100 text-green-800 border-green-300"
        } else if (confidence === 'medium') {
            badgeClasses += " bg-yellow-100 text-yellow-800 border-yellow-300"
        } else if (confidence === 'low') {
            badgeClasses += " bg-red-100 text-red-800 border-red-300"
        } else {
            badgeClasses += " bg-gray-100 text-gray-800 border-gray-300"
        }
    }

    // Show percentage if available, otherwise just the confidence level
    const displayText = percentage !== null
        ? `${percentage}%`
        : (confidence || 'unknown')

    return (
        <Badge variant="outline" className={badgeClasses}>
            {displayText}
        </Badge>
    )
}

/**
 * Renders a single content block based on its type
 */
function BlockRenderer({
    blockIdx,
    block,
    showEmpty,
    edits,
    newFields,
    onFieldEdit,
    onTableCellEdit,
    onAddField,
    onRemoveNewField
}: {
    blockIdx: number
    block: ContentBlock
    showEmpty: boolean
    edits: Record<string, string>
    newFields: Array<{ label: string; value: string }>
    onFieldEdit: (fieldKey: string, newValue: string) => void
    onTableCellEdit: (cellKey: string, newValue: string) => void
    onAddField: (blockIdx: number, label: string, value: string) => void
    onRemoveNewField: (blockIdx: number, fieldIdx: number) => void
}) {
    const { type, content } = block

    // Skip empty Figure blocks (logos/images)
    if (type === "Figure" && !content) {
        return null
    }

    // Render Title blocks as headers
    if (type === "Title") {
        const confidenceBadge = getConfidenceBadge(block.confidence, block.granular_confidence)
        const fieldKey = `title_${blockIdx}_${block.bbox?.page || 0}`
        const currentValue = edits[fieldKey] !== undefined ? edits[fieldKey] : content

        return (
            <EditableTextBlock
                fieldKey={fieldKey}
                value={currentValue}
                onEdit={onFieldEdit}
                confidenceBadge={confidenceBadge}
                className="text-center py-3 border-b-2 border-primary/20"
                textClassName="text-xl font-bold text-primary uppercase tracking-wide"
            />
        )
    }

    // Render Key Value blocks (contains multiple field:value pairs)
    if (type === "Key Value") {
        return (
            <KeyValueBlock
                blockIdx={blockIdx}
                content={content || ''}
                showEmpty={showEmpty}
                block={block}
                edits={edits}
                newFields={newFields}
                onFieldEdit={onFieldEdit}
                onAddField={onAddField}
                onRemoveNewField={onRemoveNewField}
            />
        )
    }

    // Render Section Header blocks
    if (type === "Section Header") {
        const confidenceBadge = getConfidenceBadge(block.confidence, block.granular_confidence)
        const fieldKey = `section_header_${blockIdx}_${block.bbox?.page || 0}`
        const currentValue = edits[fieldKey] !== undefined ? edits[fieldKey] : content

        return (
            <EditableTextBlock
                fieldKey={fieldKey}
                value={currentValue}
                onEdit={onFieldEdit}
                confidenceBadge={confidenceBadge}
                className="py-3 border-b border-primary/30"
                textClassName="text-lg font-bold text-primary"
            />
        )
    }

    // Render Table blocks
    if (type === "Table") {
        const confidenceBadge = getConfidenceBadge(block.confidence, block.granular_confidence)

        console.log('🎯 Rendering Table block:', {
            blockIdx,
            contentPreview: content ? content.substring(0, 200) : '[No content]',
            hasHtmlTags: content ? /<[^>]+>/.test(content) : false,
            hasOnTableCellEdit: !!onTableCellEdit,
            editsCount: Object.keys(edits || {}).length
        })

        return (
            <div className="py-4 border-2 border-red-500">
                <div className="flex items-center gap-2 mb-3">
                    <Badge variant="outline" className="text-xs bg-purple-50 text-purple-700 border-purple-300">
                        Table Block
                    </Badge>
                    {/<[^>]+>/.test(content) && (
                        <Badge variant="outline" className="text-xs bg-green-50 text-green-700 border-green-300">
                            HTML
                        </Badge>
                    )}
                    {confidenceBadge}
                </div>
                <div className="bg-yellow-100 p-2 text-xs">
                    DEBUG: Table block content starts with {content ? content.substring(0, 50) : '[No content]'}...
                </div>
                <TableRenderer
                    content={content || ''}
                    confidence={block.confidence}
                    granularConfidence={block.granular_confidence}
                    onEdit={onTableCellEdit}
                    edits={edits}
                />
            </div>
        )
    }

    // Render Text blocks
    // Text blocks can contain either:
    // 1. Multiple field:value pairs (treat like Key Value block)
    // 2. Table structures (complex or simple)
    // 3. Standalone text (display as-is)
    if (type === "Text") {
        // Skip very short empty-looking text
        if (!showEmpty && (!content || content.trim() === "<empty>")) {
            return null
        }

        // NEW: Check if this text block contains table content
        const hasHtmlTableTags = content ? /&lt;\s*(?:table|tr|td|th)\s*&gt;|<\s*(?:table|tr|td|th)\s*>/i.test(content) : false

        if (isTableContent(content || '') || hasHtmlTableTags) {
            const isComplex = detectComplexTable(content || '')
            const confidenceBadge = getConfidenceBadge(block.confidence, block.granular_confidence)

            // Debug logging
            console.log('🔍 Table detected in block:', {
                blockIndex: blockIdx,
                contentType: block.type,
                isComplex,
                contentPreview: content ? content.substring(0, 200) : '[No content]',
                hasHtmlTags: content ? /<[^>]+>/.test(content) : false,
                hasHtmlTableTags,
                forced: hasHtmlTableTags && !isTableContent(content)
            })

            return (
                <div className="py-4">
                    <div className="flex items-center gap-2 mb-3">
                        <Badge variant="outline" className="text-xs bg-blue-50 text-blue-700 border-blue-300">
                            {isComplex ? "Complex Table" : "Table"}
                        </Badge>
                        {hasHtmlTableTags && (
                            <Badge variant="outline" className="text-xs bg-green-50 text-green-700 border-green-300">
                                HTML
                            </Badge>
                        )}
                        {confidenceBadge}
                    </div>
                    <TableRenderer
                        content={content}
                        confidence={block.confidence}
                        granularConfidence={block.granular_confidence}
                    />
                </div>
            )
        }

        // Check if this text block contains field:value patterns
        const hasFieldPattern = content ? /[A-Z][^:]*:\s*\w/m.test(content) : false

        // Additional check for HTML content
        const hasHtmlContent = content ? /&lt;(?:table|tr|td|th)&gt;|<(?:table|tr|td|th)/i.test(content) : false

        if (hasHtmlContent && !isTableContent(content || '')) {
            console.log('🚨 HTML content found but not detected as table:', {
                blockIndex: blockIdx,
                content: content ? content.substring(0, 300) : '[No content]'
            })
        }

        if (hasFieldPattern) {
            // Parse as fields (same as Key Value block)
            return (
                <KeyValueBlock
                    blockIdx={blockIdx}
                    content={content || ''}
                    showEmpty={showEmpty}
                    block={block}
                    edits={edits}
                    newFields={newFields}
                    onFieldEdit={onFieldEdit}
                    onAddField={onAddField}
                    onRemoveNewField={onRemoveNewField}
                />
            )
        }

        // Otherwise display as standalone text
        const confidenceBadge = getConfidenceBadge(block.confidence, block.granular_confidence)
        const fieldKey = `text_${blockIdx}_${block.bbox?.page || 0}_${block.bbox?.top || 0}`
        const currentValue = edits[fieldKey] !== undefined ? edits[fieldKey] : content

        return (
            <EditableTextBlock
                fieldKey={fieldKey}
                value={currentValue}
                onEdit={onFieldEdit}
                confidenceBadge={confidenceBadge}
                className="py-1 border-l-2 border-primary/30 pl-3"
                textClassName="text-sm font-medium text-foreground/90"
            />
        )
    }

    // Default: render content as-is (but make it editable!)
    const fieldKey = `default_${type}_${blockIdx}_${block.bbox?.page || 0}`
    const currentValue = edits[fieldKey] !== undefined ? edits[fieldKey] : content

    return (
        <div className="py-2 border-l-2 border-muted pl-3">
            <Badge variant="outline" className="mb-2 text-xs">
                {type}
            </Badge>
            <EditableTextBlock
                fieldKey={fieldKey}
                value={currentValue}
                onEdit={onFieldEdit}
                className=""
                textClassName="text-sm whitespace-pre-wrap"
            />
        </div>
    )
}

/**
 * Parse and render Key Value block (contains multiple "Field: Value" pairs)
 * Handles both newline-separated and inline fields
 */
function KeyValueBlock({
    blockIdx,
    content,
    showEmpty,
    block,
    edits,
    newFields,
    onFieldEdit,
    onAddField,
    onRemoveNewField
}: {
    blockIdx: number
    content: string
    showEmpty: boolean
    block: ContentBlock
    edits: Record<string, string>
    newFields: Array<{ label: string; value: string }>
    onFieldEdit: (fieldKey: string, newValue: string) => void
    onAddField: (blockIdx: number, label: string, value: string) => void
    onRemoveNewField: (blockIdx: number, fieldIdx: number) => void
}) {
    const [isEditing, setIsEditing] = useState(false)
    const [editValue, setEditValue] = useState(content || "")

    // Handle undefined content
    if (!content) {
        return (
            <Card className="p-4">
                <p className="text-muted-foreground text-sm">No content available</p>
            </Card>
        )
    }

    // Create unique field key for this block
    const fieldKey = `keyvalue_${blockIdx}_${block.bbox?.page || 0}`
    const currentValue = edits[fieldKey] !== undefined ? edits[fieldKey] : content

    const handleSave = () => {
        if (editValue !== content) {
            onFieldEdit(fieldKey, editValue)
        }
        setIsEditing(false)
    }

    const handleCancel = () => {
        setEditValue(currentValue)
        setIsEditing(false)
    }

    const confidenceBadge = getConfidenceBadge(block.confidence, block.granular_confidence)

    return (
        <div className="space-y-2 bg-muted/30 p-4 rounded-lg border border-border">
            {/* Confidence Badge */}
            {confidenceBadge && (
                <div className="flex items-center gap-2 mb-2">
                    <Badge variant="outline" className="text-xs bg-blue-50 text-blue-700 border-blue-300">
                        Key Value Block
                    </Badge>
                    {confidenceBadge}
                </div>
            )}

            {/* Content Display - Preserve Original Formatting */}
            {isEditing ? (
                <div className="space-y-2">
                    <textarea
                        value={editValue}
                        onChange={(e) => setEditValue(e.target.value)}
                        className="w-full min-h-[200px] p-3 text-sm font-mono border rounded-md focus:ring-2 focus:ring-primary focus:border-transparent resize-y"
                        autoFocus
                    />
                    <div className="flex items-center gap-2">
                        <Button size="sm" onClick={handleSave}>
                            <Save className="w-4 h-4 mr-2" />
                            Save
                        </Button>
                        <Button size="sm" variant="outline" onClick={handleCancel}>
                            <X className="w-4 h-4 mr-2" />
                            Cancel
                        </Button>
                    </div>
                </div>
            ) : (
                <div
                    onClick={() => setIsEditing(true)}
                    className="cursor-pointer hover:bg-muted/50 p-3 rounded-md transition-colors"
                    title="Click to edit"
                >
                    <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed text-foreground">
                        {currentValue}
                    </pre>
                </div>
            )}
        </div>
    )
}

/**
 * Render a single field row (label: value) with confidence badge and inline editing
 */
function FieldRow({
    fieldKey,
    label,
    value,
    isEmpty,
    confidence,
    granularConfidence,
    onEdit
}: {
    fieldKey: string
    label: string
    value: string
    isEmpty: boolean
    confidence?: string
    granularConfidence?: {
        extract_confidence?: number | null
        parse_confidence?: number | null
    }
    onEdit: (fieldKey: string, newValue: string) => void
}) {
    const [isEditingValue, setIsEditingValue] = useState(false)
    const [isEditingLabel, setIsEditingLabel] = useState(false)
    const [editValue, setEditValue] = useState(value)
    const [editLabel, setEditLabel] = useState(label)

    // Use shared confidence badge function
    const confidenceBadgeElement = getConfidenceBadge(confidence, granularConfidence)

    // Handle standalone text without label
    if (!label) {
        const handleSaveStandalone = () => {
            if (editValue !== value) {
                onEdit(fieldKey, editValue)
            }
            setIsEditingValue(false)
        }

        const handleKeyDownStandalone = (e: React.KeyboardEvent) => {
            if (e.key === 'Enter') {
                handleSaveStandalone()
            } else if (e.key === 'Escape') {
                setEditValue(value)
                setIsEditingValue(false)
            }
        }

        return (
            <div className="py-2 border-b border-border/30">
                <div className="flex items-start gap-3">
                    {isEditingValue ? (
                        <input
                            type="text"
                            value={editValue}
                            onChange={(e) => setEditValue(e.target.value)}
                            onKeyDown={handleKeyDownStandalone}
                            onBlur={handleSaveStandalone}
                            autoFocus
                            className="flex-1 px-2 py-1 text-sm font-medium border border-primary rounded focus:outline-none focus:ring-2 focus:ring-primary"
                            style={{whiteSpace: 'normal', wordWrap: 'break-word'}}
                        />
                    ) : (
                        <div
                            onClick={() => setIsEditingValue(true)}
                            className="flex-1 py-1 text-sm font-medium cursor-pointer hover:bg-muted/50 px-2 rounded transition-colors"
                            style={{whiteSpace: 'normal', wordWrap: 'break-word'}}
                        >
                            {value}
                        </div>
                    )}
                    <div className="shrink-0">
                        {confidenceBadgeElement}
                    </div>
                </div>
            </div>
        )
    }

    const handleSaveValue = () => {
        if (editValue !== value) {
            onEdit(fieldKey, editValue)
        }
        setIsEditingValue(false)
    }

    const handleCancelValue = () => {
        setEditValue(value)
        setIsEditingValue(false)
    }

    const handleSaveLabel = () => {
        if (editLabel !== label) {
            onEdit(`${fieldKey}_label`, editLabel)
        }
        setIsEditingLabel(false)
    }

    const handleCancelLabel = () => {
        setEditLabel(label)
        setIsEditingLabel(false)
    }

    const handleKeyDownValue = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter') {
            handleSaveValue()
        } else if (e.key === 'Escape') {
            handleCancelValue()
        }
    }

    const handleKeyDownLabel = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter') {
            handleSaveLabel()
        } else if (e.key === 'Escape') {
            handleCancelLabel()
        }
    }

    return (
        <div className={`py-2 border-b border-border/30 last:border-0 ${isEmpty ? 'opacity-50' : ''}`}>
            <div className="flex items-start gap-3">
                {/* Editable Label */}
                <div className="font-semibold text-sm text-foreground shrink-0" style={{maxWidth: '300px'}}>
                    {isEditingLabel ? (
                        <input
                            type="text"
                            value={editLabel}
                            onChange={(e) => setEditLabel(e.target.value)}
                            onKeyDown={handleKeyDownLabel}
                            onBlur={handleSaveLabel}
                            autoFocus
                            className="w-full px-2 py-1 border border-primary rounded focus:outline-none focus:ring-2 focus:ring-primary bg-background"
                        />
                    ) : (
                        <span
                            onClick={() => setIsEditingLabel(true)}
                            className="cursor-pointer hover:bg-muted/50 px-2 py-1 rounded transition-colors inline-block"
                        >
                            {label}
                        </span>
                    )}
                </div>
                {/* Editable Value */}
                <div className="flex-1 min-w-0">
                    {isEditingValue ? (
                        <div className="flex items-center gap-2">
                            <input
                                type="text"
                                value={editValue}
                                onChange={(e) => setEditValue(e.target.value)}
                                onKeyDown={handleKeyDownValue}
                                onBlur={handleSaveValue}
                                autoFocus
                                className="flex-1 px-2 py-1 text-sm border border-primary rounded focus:outline-none focus:ring-2 focus:ring-primary"
                            />
                        </div>
                    ) : (
                        <div
                            onClick={() => setIsEditingValue(true)}
                            className={`text-sm cursor-pointer hover:bg-muted/50 px-2 py-1 rounded transition-colors ${
                                isEmpty ? 'text-muted-foreground italic' : 'font-medium'
                            }`}
                        >
                            {value}
                        </div>
                    )}
                </div>
                <div className="flex items-center shrink-0">
                    {confidenceBadgeElement}
                </div>
            </div>
        </div>
    )
}
