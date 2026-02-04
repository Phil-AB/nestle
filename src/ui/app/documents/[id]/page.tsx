"use client"

// API URL configuration - reads from environment or uses default
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://54.87.52.48:8000/api/v1"

import { useEffect, useState, useMemo } from "react"
import { useParams, useRouter } from "next/navigation"
import { apiClient, type DocumentResponse } from "@/lib/api-client"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Loader, ArrowLeft, AlertCircle, CheckCircle, FileText, RefreshCw, Eye, EyeOff, FileImage, Download, Layers, GripVertical } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import {
    formatDocumentFields,
    sortFieldsSpatially,
    formatValueForDisplay,
    type FormattedField
} from "@/lib/document-formatter"
import { BlocksDocumentViewer } from "@/components/blocks-document-viewer"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { DocumentViewerWrapper } from "@/components/document-viewer-wrapper"
import GenerationButton from "@/components/generation-button"
import { BBoxDocumentRenderer } from "@/components/documents/BBoxDocumentRenderer"

export default function DocumentRenderPage() {
    const params = useParams()
    const router = useRouter()
    const documentId = params.id as string

    const [document, setDocument] = useState<DocumentResponse | null>(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const [polling, setPolling] = useState(false)
    const [showEmpty, setShowEmpty] = useState(true) // Show empty by default to preserve structure
    const [pages, setPages] = useState<any[]>([])
    const [pagesLoading, setPagesLoading] = useState(false)
    const [rawData, setRawData] = useState<any>(null) // For dynamic renderer

    const loadDocument = async () => {
        try {
            const doc = await apiClient.getDocument(documentId, {
                includeRawData: false,
                includeLayout: false
            })
            setDocument(doc)
            setError(null)

            // Also fetch raw data for dynamic renderer
            try {
                const response = await fetch(
                    `${API_BASE_URL}/documents/${documentId}?format=raw`,
                    { headers: { 'X-API-Key': 'dev-key-12345' } }
                )
                if (response.ok) {
                    const raw = await response.json()
                    setRawData(raw)
                }
            } catch (rawError) {
                console.warn("Failed to load raw data:", rawError)
                // Continue without raw data
            }

            if (doc.extraction_status === 'processing') {
                setPolling(true)
            } else {
                setPolling(false)
            }
        } catch (err: any) {
            console.error("Failed to load document:", err)
            setError(err.message || "Failed to load document")
            setPolling(false)
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => {
        if (documentId) {
            loadDocument()
        }
    }, [documentId])

    const loadPages = async () => {
        if (!document?.is_multi_page) return

        try {
            setPagesLoading(true)
            const response = await apiClient.getDocumentPages(documentId)
            setPages(response.pages || [])
        } catch (err: any) {
            console.error("Failed to load pages:", err)
        } finally {
            setPagesLoading(false)
        }
    }

    useEffect(() => {
        if (document?.is_multi_page) {
            loadPages()
        }
    }, [document, documentId])

    useEffect(() => {
        if (!polling) return

        const interval = setInterval(() => {
            loadDocument()
        }, 2000)

        return () => clearInterval(interval)
    }, [polling, documentId])

    // Process and sort fields by spatial position
    const { sortedFields, stats } = useMemo(() => {
        if (!document) return { sortedFields: [], stats: { total: 0, populated: 0, empty: 0 } }

        const formatted = formatDocumentFields(document.fields)
        const sorted = sortFieldsSpatially(formatted, document.fields)

        const stats = {
            total: formatted.length,
            populated: formatted.filter(f => !f.isEmpty).length,
            empty: formatted.filter(f => f.isEmpty).length,
        }

        // Filter based on show empty toggle
        const visible = showEmpty ? sorted : sorted.filter(f => !f.isEmpty)

        return { sortedFields: visible, stats }
    }, [document, showEmpty])

    if (loading && !document) {
        return (
            <div className="flex justify-center items-center min-h-screen">
                <Loader className="w-8 h-8 animate-spin text-primary" />
            </div>
        )
    }

    if (error && !document) {
        return (
            <div className="p-8 max-w-6xl mx-auto">
                <Button onClick={() => router.push('/documents')} variant="outline" className="mb-6">
                    <ArrowLeft className="w-4 h-4 mr-2" />
                    Back to Documents
                </Button>
                <Card className="p-8 text-center">
                    <AlertCircle className="w-12 h-12 text-destructive mx-auto mb-4" />
                    <h2 className="text-xl font-bold mb-2">Error Loading Document</h2>
                    <p className="text-muted-foreground">{error}</p>
                </Card>
            </div>
        )
    }

    if (!document) {
        return null
    }

    const isProcessing = document.extraction_status === 'processing'
    const isComplete = document.extraction_status === 'complete'
    const isFailed = document.extraction_status === 'failed'

    return (
        <div className="p-8 max-w-7xl mx-auto w-full">
            {/* Header */}
            <div className="flex items-center justify-between mb-6">
                <Button onClick={() => router.push('/documents')} variant="outline">
                    <ArrowLeft className="w-4 h-4 mr-2" />
                    Back to Documents
                </Button>
                <div className="flex gap-2">
                    {isComplete && (
                        <>
                            <GenerationButton
                                documentId={document.document_id}
                                documentType={document.document_type}
                            />
                            <Button
                                onClick={async () => {
                                    try {
                                        // Fetch raw Reducto format from API
                                        const response = await fetch(
                                            `${API_BASE_URL}/documents/${document.document_id}?format=raw`,
                                            { headers: { 'X-API-Key': 'dev-key-12345' } }
                                        )
                                        const rawData = await response.json()
                                        const jsonData = JSON.stringify(rawData, null, 2)
                                        const blob = new Blob([jsonData], { type: 'application/json' })
                                        const url = window.URL.createObjectURL(blob)
                                        const a = window.document.createElement('a')
                                        a.href = url
                                        a.download = `${document.document_type}_${document.document_id}_raw.json`
                                        window.document.body.appendChild(a)
                                        a.click()
                                        window.URL.revokeObjectURL(url)
                                        window.document.body.removeChild(a)
                                    } catch (error) {
                                        console.error('Failed to download raw JSON:', error)
                                        // Fallback to normalized format
                                        const jsonData = JSON.stringify(document, null, 2)
                                        const blob = new Blob([jsonData], { type: 'application/json' })
                                        const url = window.URL.createObjectURL(blob)
                                        const a = window.document.createElement('a')
                                        a.href = url
                                        a.download = `${document.document_type}_${document.document_id}.json`
                                        window.document.body.appendChild(a)
                                        a.click()
                                        window.URL.revokeObjectURL(url)
                                        window.document.body.removeChild(a)
                                    }
                                }}
                                variant="outline"
                                size="sm"
                            >
                                <Download className="w-4 h-4 mr-2" />
                                Download Raw JSON
                            </Button>
                        </>
                    )}
                    <Button onClick={loadDocument} variant="outline" size="sm" disabled={loading}>
                        <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
                        Refresh
                    </Button>
                </div>
            </div>

            {/* Document Header Card */}
            <Card className="p-6 mb-6">
                <div className="flex items-start justify-between">
                    <div className="flex items-start gap-4 flex-1">
                        <div className="p-3 bg-primary/10 rounded-lg">
                            <FileText className="w-8 h-8 text-primary" />
                        </div>
                        <div className="flex-1">
                            <h1 className="text-3xl font-bold mb-2">
                                {document.document_number || document.document_type.replace(/_/g, ' ').toUpperCase()}
                            </h1>
                            <div className="flex items-center gap-4 text-sm text-muted-foreground flex-wrap">
                                <span className="capitalize font-medium">{document.document_type.replace(/_/g, ' ')}</span>
                                <span>•</span>
                                <span>{new Date(document.created_at).toLocaleString()}</span>
                                {document.metadata?.page_count && (
                                    <>
                                        <span>•</span>
                                        <span>{document.metadata.page_count} page{document.metadata.page_count > 1 ? 's' : ''}</span>
                                    </>
                                )}
                            </div>
                        </div>
                    </div>
                    <div className="flex flex-col items-end gap-2">
                        <span className={`px-4 py-2 rounded-full text-sm font-semibold ${
                            isComplete ? 'bg-green-100 text-green-700' :
                            isFailed ? 'bg-red-100 text-red-700' :
                            'bg-yellow-100 text-yellow-700'
                        }`}>
                            {isProcessing && <Loader className="w-4 h-4 inline-block mr-2 animate-spin" />}
                            {isComplete && <CheckCircle className="w-4 h-4 inline-block mr-2" />}
                            {isFailed && <AlertCircle className="w-4 h-4 inline-block mr-2" />}
                            {document.extraction_status}
                        </span>
                    </div>
                </div>
            </Card>

            {/* Processing Status */}
            {isProcessing && (
                <Card className="p-8 mb-6 text-center">
                    <Loader className="w-12 h-12 animate-spin text-primary mx-auto mb-4" />
                    <h2 className="text-xl font-bold mb-2">Extracting Document Data</h2>
                    <p className="text-muted-foreground">
                        Parsing and extracting fields from your document. This may take a few moments...
                    </p>
                </Card>
            )}

            {/* Failed Status */}
            {isFailed && (
                <Card className="p-8 mb-6 border-l-4 border-red-500">
                    <div className="flex items-start gap-4">
                        <AlertCircle className="w-6 h-6 text-red-600 mt-1" />
                        <div>
                            <h2 className="text-xl font-bold mb-2">Extraction Failed</h2>
                            <p className="text-muted-foreground">
                                The document could not be processed. Please try uploading again.
                            </p>
                        </div>
                    </div>
                </Card>
            )}

            {/* Document Content - Tabbed Interface */}
            {isComplete && (
                <Tabs defaultValue="dynamic" className="w-full">
                    <TabsList className={`grid w-full mb-6 ${document.is_multi_page ? 'grid-cols-4' : 'grid-cols-3'}`}>
                        <TabsTrigger value="dynamic" className="flex items-center gap-2">
                            <GripVertical className="w-4 h-4" />
                            Dynamic View
                        </TabsTrigger>
                        <TabsTrigger value="original" className="flex items-center gap-2">
                            <FileImage className="w-4 h-4" />
                            Original Document
                        </TabsTrigger>
                        <TabsTrigger value="extracted" className="flex items-center gap-2">
                            <FileText className="w-4 h-4" />
                            Extracted Data
                        </TabsTrigger>
                        {document.is_multi_page && (
                            <TabsTrigger value="pages" className="flex items-center gap-2">
                                <Layers className="w-4 h-4" />
                                Pages ({document.total_pages || 0})
                            </TabsTrigger>
                        )}
                    </TabsList>

                    {/* Tab 1: Dynamic View - Uses raw bbox coordinates */}
                    <TabsContent value="dynamic">
                        {rawData ? (
                            <BBoxDocumentRenderer
                                rawData={rawData}
                                documentId={documentId}
                                className="h-[800px]"
                            />
                        ) : (
                            <Card className="p-8 text-center">
                                <GripVertical className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
                                <h2 className="text-xl font-bold mb-2">Dynamic View Not Available</h2>
                                <p className="text-muted-foreground mb-4">
                                    Raw Reducto data is required for dynamic rendering. Make sure document has been processed with bbox-aware extraction.
                                </p>
                                <Button onClick={loadDocument} variant="outline">
                                    <RefreshCw className="w-4 h-4 mr-2" />
                                    Reload Document
                                </Button>
                            </Card>
                        )}
                    </TabsContent>

                    {/* Tab 2: Original Document Viewer */}
                    <TabsContent value="original">
                        <Card className="p-6">
                            <DocumentViewerWrapper
                                fileUrl={apiClient.getDocumentFileUrl(documentId)}
                                fileType={document.mime_type || undefined}
                                blocks={document.blocks}
                            />
                        </Card>
                    </TabsContent>

                    {/* Tab 2: Extracted Data (existing content) */}
                    <TabsContent value="extracted" className="w-full" style={{minWidth: '0'}}>
                        {document.blocks && document.blocks.length > 0 ? (
                            /* New: Blocks-based rendering (shows ALL content including titles, text) */
                            <>
                                <Card className="p-4 mb-6">
                                    <div className="flex items-center justify-between flex-wrap gap-4">
                                        <div className="flex items-center gap-4">
                                            <div className="flex items-center gap-2 text-sm">
                                                <span className="text-muted-foreground">Content Blocks:</span>
                                                <Badge variant="secondary">{document.blocks.length}</Badge>
                                            </div>
                                            <div className="flex items-center gap-2 text-sm">
                                                <span className="text-muted-foreground">Fields:</span>
                                                <Badge variant="default">{stats.populated}</Badge>
                                            </div>
                                        </div>
                                        <Button
                                            variant="outline"
                                            size="sm"
                                            onClick={() => setShowEmpty(!showEmpty)}
                                        >
                                            {showEmpty ? (
                                                <><EyeOff className="w-4 h-4 mr-2" /> Hide Empty</>
                                            ) : (
                                                <><Eye className="w-4 h-4 mr-2" /> Show Empty</>
                                            )}
                                        </Button>
                                    </div>
                                </Card>
                                <BlocksDocumentViewer
                                    blocks={document.blocks}
                                    showEmpty={showEmpty}
                                    documentId={documentId}
                                />
                            </>
                        ) : sortedFields.length > 0 ? (
                            /* Fallback: Fields-only rendering (for older documents without blocks) */
                            <>
                                <Card className="p-4 mb-6">
                                    <div className="flex items-center justify-between flex-wrap gap-4">
                                        <div className="flex items-center gap-4">
                                            <div className="flex items-center gap-2 text-sm">
                                                <span className="text-muted-foreground">Total Fields:</span>
                                                <Badge variant="secondary">{stats.total}</Badge>
                                            </div>
                                            <div className="flex items-center gap-2 text-sm">
                                                <span className="text-muted-foreground">Populated:</span>
                                                <Badge variant="default">{stats.populated}</Badge>
                                            </div>
                                            {stats.empty > 0 && (
                                                <div className="flex items-center gap-2 text-sm">
                                                    <span className="text-muted-foreground">Empty:</span>
                                                    <Badge variant="outline">{stats.empty}</Badge>
                                                </div>
                                            )}
                                        </div>
                                        <Button
                                            variant="outline"
                                            size="sm"
                                            onClick={() => setShowEmpty(!showEmpty)}
                                        >
                                            {showEmpty ? (
                                                <><EyeOff className="w-4 h-4 mr-2" /> Hide Empty ({stats.empty})</>
                                            ) : (
                                                <><Eye className="w-4 h-4 mr-2" /> Show Empty ({stats.empty})</>
                                            )}
                                        </Button>
                                    </div>
                                </Card>
                                <Card className="p-8" style={{width: '100%', minWidth: '0'}}>
                                    <div className="space-y-1">
                                        {sortedFields.map((field) => (
                                            <DocumentField key={field.key} field={field} />
                                        ))}
                                    </div>
                                </Card>
                            </>
                        ) : null}
                    </TabsContent>

                    {/* Tab 3: Pages (for multi-page documents) */}
                    {document.is_multi_page && (
                        <TabsContent value="pages">
                            <Card className="p-6">
                                <div className="flex items-center justify-between mb-6">
                                    <h3 className="text-lg font-semibold">Document Pages</h3>
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        onClick={loadPages}
                                        disabled={pagesLoading}
                                    >
                                        {pagesLoading ? (
                                            <><Loader className="w-4 h-4 mr-2 animate-spin" /> Refreshing...</>
                                        ) : (
                                            <><RefreshCw className="w-4 h-4 mr-2" /> Refresh</>
                                        )}
                                    </Button>
                                </div>

                                {pagesLoading ? (
                                    <div className="flex justify-center py-12">
                                        <Loader className="w-8 h-8 animate-spin text-primary" />
                                    </div>
                                ) : pages.length === 0 ? (
                                    <div className="text-center py-12 text-muted-foreground">
                                        No pages found for this document.
                                    </div>
                                ) : (
                                    <div className="space-y-4">
                                        {pages.map((page, index) => (
                                            <div key={page.page_id} className="flex items-center justify-between p-4 bg-muted rounded-lg border">
                                                <div className="flex items-center gap-4">
                                                    <span className="text-sm font-medium text-muted-foreground w-8">
                                                        {page.page_number}
                                                    </span>
                                                    <div>
                                                        <p className="font-medium break-words">{page.file_name}</p>
                                                        <div className="flex items-center gap-4 mt-1">
                                                            <span className="text-sm text-muted-foreground">
                                                                {(page.file_size / 1024).toFixed(2)} KB
                                                            </span>
                                                            <Badge
                                                                variant={
                                                                    page.extraction_status === 'completed' ? 'default' :
                                                                    page.extraction_status === 'processing' ? 'secondary' :
                                                                    page.extraction_status === 'failed' ? 'destructive' :
                                                                    'outline'
                                                                }
                                                            >
                                                                {page.extraction_status}
                                                            </Badge>
                                                        </div>
                                                        {page.error_message && (
                                                            <p className="text-sm text-destructive mt-1 break-words">{page.error_message}</p>
                                                        )}
                                                    </div>
                                                </div>
                                                <Button
                                                    variant="outline"
                                                    size="sm"
                                                    onClick={() => {
                                                        apiClient.downloadPage(documentId, page.page_number).then(blob => {
                                                            const url = window.URL.createObjectURL(blob)
                                                            const a = document.createElement('a')
                                                            a.href = url
                                                            a.download = page.file_name
                                                            document.body.appendChild(a)
                                                            a.click()
                                                            window.URL.revokeObjectURL(url)
                                                            document.body.removeChild(a)
                                                        }).catch(err => {
                                                            console.error('Failed to download page:', err)
                                                        })
                                                    }}
                                                >
                                                    <Download className="w-4 h-4 mr-2" />
                                                    Download
                                                </Button>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </Card>
                        </TabsContent>
                    )}
                </Tabs>
            )}

            {/* Extracted Items (Tables) */}
            {isComplete && document.items && document.items.length > 0 && (
                <Card className="p-6 mt-6">
                    <h2 className="text-2xl font-bold mb-4">Line Items ({document.items.length})</h2>
                    <div className="overflow-x-auto">
                        <table className="w-full border-collapse">
                            <thead>
                                <tr className="border-b-2 border-border bg-muted/50">
                                    <th className="text-left p-3 font-semibold">#</th>
                                    {Object.keys(document.items[0] || {}).map(key => {
                                        if (key.startsWith('_') || ['column_index', 'column_number', 'row_index', 'table_block_index', 'table_bbox', 'normalized_header', 'original_header', 'original_page'].includes(key)) {
                                            return null
                                        }
                                        return (
                                            <th key={key} className="text-left p-3 font-semibold">
                                                {key.replace(/_/g, ' ').replace(/^\d+\s*/, '').split(' ').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')}
                                            </th>
                                        )
                                    })}
                                </tr>
                            </thead>
                            <tbody>
                                {document.items.map((item, idx) => (
                                    <tr key={idx} className="border-b hover:bg-muted/30 transition-colors">
                                        <td className="p-3 font-medium text-muted-foreground">{idx + 1}</td>
                                        {Object.entries(item).map(([key, value]) => {
                                            if (key.startsWith('_') || ['column_index', 'column_number', 'row_index', 'table_block_index', 'table_bbox', 'normalized_header', 'original_header', 'original_page'].includes(key)) {
                                                return null
                                            }

                                            let displayValue = value
                                            if (typeof value === 'object' && value !== null && 'value' in value) {
                                                displayValue = (value as any).value
                                            }

                                            return (
                                                <td key={key} className="p-3">
                                                    {typeof displayValue === 'object' && displayValue !== null
                                                        ? JSON.stringify(displayValue)
                                                        : String(displayValue || '-')}
                                                </td>
                                            )
                                        })}
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </Card>
            )}

            {/* No Data Extracted */}
            {isComplete && sortedFields.length === 0 && (!document.items || document.items.length === 0) && (
                <Card className="p-12 text-center">
                    <FileText className="w-16 h-16 text-muted-foreground mx-auto mb-4" />
                    <h2 className="text-xl font-bold mb-2">No Data Extracted</h2>
                    <p className="text-muted-foreground">
                        No fields or items were extracted from this document.
                    </p>
                </Card>
            )}

            {/* Metadata */}
            {document.metadata && (
                <Card className="p-6 mt-6">
                    <h2 className="text-xl font-bold mb-4">Extraction Metadata</h2>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                        <div>
                            <p className="text-muted-foreground mb-1">Provider</p>
                            <p className="font-medium capitalize">{document.metadata.provider}</p>
                        </div>
                        {document.metadata.extraction_duration && (
                            <div>
                                <p className="text-muted-foreground mb-1">Duration</p>
                                <p className="font-medium">{document.metadata.extraction_duration.toFixed(2)}s</p>
                            </div>
                        )}
                        {document.metadata.confidence && (
                            <div>
                                <p className="text-muted-foreground mb-1">Confidence</p>
                                <p className="font-medium">{(document.metadata.confidence * 100).toFixed(1)}%</p>
                            </div>
                        )}
                        {document.metadata.job_id && (
                            <div>
                                <p className="text-muted-foreground mb-1">Job ID</p>
                                <p className="font-medium font-mono text-xs break-all">{document.metadata.job_id}</p>
                            </div>
                        )}
                    </div>
                </Card>
            )}
        </div>
    )
}

// Document Field Component - displays a single field in document format
function DocumentField({ field }: { field: FormattedField }) {
    const displayValue = formatValueForDisplay(field)

    // Detect if this is a multi-line field (value has newlines or is very long)
    const isMultiLine = displayValue.includes('\n') || displayValue.length > 80

    return (
        <div className={`py-2 border-b border-border/30 last:border-0 ${field.isEmpty ? 'opacity-60' : ''}`}>
            <div className={isMultiLine ? "flex flex-col gap-1" : "grid grid-cols-[auto_1fr] gap-3 items-start"}>
                {/* Field Label */}
                <div className="font-semibold text-sm text-foreground pr-4">
                    {field.displayName}:
                </div>

                {/* Field Value */}
                <div className={`${field.isEmpty ? 'text-muted-foreground italic' : 'font-medium'} ${isMultiLine ? 'whitespace-pre-wrap' : ''} break-all`} style={{wordWrap: 'break-word', overflowWrap: 'break-word'}}>
                    {displayValue}
                </div>
            </div>
        </div>
    )
}
