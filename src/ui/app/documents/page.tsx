"use client"

import { useEffect, useState } from "react"
import { api, Document } from "@/lib/api"
import { apiClient, type DocumentResponse } from "@/lib/api-client"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Loader, FileText, CheckCircle, AlertCircle, Eye, RefreshCw } from "lucide-react"

export default function DocumentsPage() {
    const [documents, setDocuments] = useState<Document[]>([])
    const [selectedDoc, setSelectedDoc] = useState<DocumentResponse | null>(null)
    const [loading, setLoading] = useState(true)
    const [loadingDetails, setLoadingDetails] = useState(false)
    const [error, setError] = useState<string | null>(null)

    useEffect(() => {
        loadDocuments()
        // Poll every 5 seconds to check for extraction updates
        const interval = setInterval(loadDocuments, 5000)
        return () => clearInterval(interval)
    }, [])

    const loadDocuments = async () => {
        try {
            const response = await api.getDocuments()
            setDocuments(response.data)
        } catch (err) {
            setError("Failed to load documents")
        } finally {
            setLoading(false)
        }
    }

    const viewDocument = async (docId: string) => {
        setLoadingDetails(true)
        try {
            const doc = await apiClient.getDocument(docId)
            setSelectedDoc(doc)
        } catch (err) {
            console.error("Failed to load document details:", err)
        } finally {
            setLoadingDetails(false)
        }
    }

    if (loading) {
        return (
            <div className="flex justify-center items-center min-h-screen">
                <Loader className="w-8 h-8 animate-spin text-primary" />
            </div>
        )
    }

    // If a document is selected, show its details
    if (selectedDoc) {
        return (
            <div className="p-8 max-w-6xl mx-auto">
                <Button onClick={() => setSelectedDoc(null)} variant="outline" className="mb-6">
                    ← Back to Documents
                </Button>

                <Card className="p-6">
                    <div className="mb-6">
                        <h1 className="text-2xl font-bold mb-2">{selectedDoc.document_number || "Document Details"}</h1>
                        <div className="flex items-center gap-4 text-sm text-muted-foreground">
                            <span className="capitalize">{selectedDoc.document_type}</span>
                            <span>•</span>
                            <span className={`px-3 py-1 rounded-full text-xs font-medium ${selectedDoc.extraction_status === 'complete' ? 'bg-green-100 text-green-700' :
                                    selectedDoc.extraction_status === 'failed' ? 'bg-red-100 text-red-700' :
                                        'bg-yellow-100 text-yellow-700'
                                }`}>
                                {selectedDoc.extraction_status}
                            </span>
                            <span>•</span>
                            <span>{new Date(selectedDoc.created_at).toLocaleString()}</span>
                        </div>
                    </div>

                    {/* Extracted Fields */}
                    {Object.keys(selectedDoc.fields).length > 0 && (
                        <div className="mb-8">
                            <h2 className="text-lg font-semibold mb-4">Extracted Fields</h2>
                            <div className="grid grid-cols-2 gap-4">
                                {Object.entries(selectedDoc.fields).map(([key, value]) => (
                                    <div key={key} className="p-4 bg-muted rounded-lg">
                                        <p className="text-xs text-muted-foreground uppercase tracking-wide mb-1">
                                            {key.replace(/_/g, ' ')}
                                        </p>
                                        <p className="font-medium">{typeof value === 'object' ? JSON.stringify(value) : String(value)}</p>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Extracted Items */}
                    {selectedDoc.items && selectedDoc.items.length > 0 && (
                        <div>
                            <h2 className="text-lg font-semibold mb-4">Line Items ({selectedDoc.items.length})</h2>
                            <div className="overflow-x-auto">
                                <table className="w-full">
                                    <thead>
                                        <tr className="border-b">
                                            <th className="text-left p-2 font-medium">#</th>
                                            {Object.keys(selectedDoc.items[0] || {}).map(key => (
                                                <th key={key} className="text-left p-2 font-medium capitalize">
                                                    {key.replace(/_/g, ' ')}
                                                </th>
                                            ))}
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {selectedDoc.items.map((item, idx) => (
                                            <tr key={idx} className="border-b">
                                                <td className="p-2">{idx + 1}</td>
                                                {Object.values(item).map((value, i) => (
                                                    <td key={i} className="p-2">
                                                        {typeof value === 'object' ? JSON.stringify(value) : String(value)}
                                                    </td>
                                                ))}
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    )}

                    {/* No data extracted */}
                    {Object.keys(selectedDoc.fields).length === 0 && selectedDoc.items.length === 0 && (
                        <div className="text-center py-12 text-muted-foreground">
                            {selectedDoc.extraction_status === 'processing' ? (
                                <>
                                    <Loader className="w-8 h-8 animate-spin mx-auto mb-4 text-primary" />
                                    <p>Extraction in progress...</p>
                                </>
                            ) : selectedDoc.extraction_status === 'failed' ? (
                                <>
                                    <AlertCircle className="w-8 h-8 mx-auto mb-4 text-destructive" />
                                    <p>Extraction failed. Please try uploading again.</p>
                                </>
                            ) : (
                                <p>No data extracted from this document.</p>
                            )}
                        </div>
                    )}
                </Card>
            </div>
        )
    }

    return (
        <div className="p-8 max-w-6xl mx-auto">
            <div className="flex items-center justify-between mb-6">
                <h1 className="text-3xl font-bold">Uploaded Documents</h1>
                <Button onClick={loadDocuments} variant="outline" size="sm">
                    <RefreshCw className="w-4 h-4 mr-2" />
                    Refresh
                </Button>
            </div>

            {error && (
                <div className="bg-destructive/10 text-destructive p-4 rounded-lg mb-6 flex items-center gap-2">
                    <AlertCircle className="w-5 h-5" />
                    {error}
                </div>
            )}

            <div className="grid gap-4">
                {documents.length === 0 ? (
                    <Card className="p-8 text-center text-muted-foreground">
                        No documents found. Upload some documents to get started.
                    </Card>
                ) : (
                    documents.map((doc) => (
                        <Card key={doc.id} className="p-4 flex items-center justify-between hover:shadow-lg transition-shadow">
                            <div className="flex items-center gap-4 flex-1">
                                <div className="p-2 bg-primary/10 rounded-lg">
                                    <FileText className="w-6 h-6 text-primary" />
                                </div>
                                <div>
                                    <h3 className="font-semibold">{doc.document_number || "Untitled"}</h3>
                                    <p className="text-sm text-muted-foreground">
                                        {doc.document_type} • {new Date(doc.created_at).toLocaleDateString()}
                                    </p>
                                </div>
                            </div>

                            <div className="flex items-center gap-4">
                                <span className={`px-3 py-1 rounded-full text-xs font-medium ${doc.extraction_status === 'complete' ? 'bg-green-100 text-green-700' :
                                        doc.extraction_status === 'failed' ? 'bg-red-100 text-red-700' :
                                            'bg-yellow-100 text-yellow-700'
                                    }`}>
                                    {doc.extraction_status}
                                </span>
                                <div className="text-sm text-muted-foreground">
                                    {doc.items_count} items
                                </div>
                                <Button onClick={() => viewDocument(doc.id)} size="sm" disabled={loadingDetails}>
                                    {loadingDetails ? <Loader className="w-4 h-4 animate-spin" /> : <Eye className="w-4 h-4" />}
                                </Button>
                            </div>
                        </Card>
                    ))
                )}
            </div>
        </div>
    )
}
