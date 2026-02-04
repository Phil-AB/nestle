"use client"

import { useState, useEffect } from "react"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Table } from "@/components/ui/table"
import { Skeleton } from "@/components/ui/skeleton"
import { apiClient, type DocumentResponse, type DocumentType, type ExtractionStatus } from "@/lib/api-client"
import { FileText, Download, Trash2, Eye, AlertCircle, CheckCircle, Clock } from "lucide-react"
import { toast } from "sonner"
import { format } from "date-fns"

interface DocumentListProps {
  onViewDocument?: (document: DocumentResponse) => void
}

export default function DocumentList({ onViewDocument }: DocumentListProps) {
  const [documents, setDocuments] = useState<DocumentResponse[]>([])
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const [filterType, setFilterType] = useState<DocumentType | "all">("all")
  const [filterStatus, setFilterStatus] = useState<ExtractionStatus | "all">("all")

  const documentTypes: { value: DocumentType | "all"; label: string }[] = [
    { value: "all", label: "All Types" },
    { value: "invoice", label: "Invoice" },
    { value: "boe", label: "Bill of Entry" },
    { value: "packing_list", label: "Packing List" },
    { value: "coo", label: "Certificate of Origin" },
    { value: "freight", label: "Freight Document" },
  ]

  const statusOptions: { value: ExtractionStatus | "all"; label: string }[] = [
    { value: "all", label: "All Status" },
    { value: "complete", label: "Complete" },
    { value: "incomplete", label: "Incomplete" },
    { value: "failed", label: "Failed" },
    { value: "processing", label: "Processing" },
  ]

  useEffect(() => {
    loadDocuments()
  }, [page, filterType, filterStatus])

  const loadDocuments = async () => {
    setLoading(true)
    try {
      const response = await apiClient.listDocuments({
        documentType: filterType === "all" ? undefined : filterType,
        status: filterStatus === "all" ? undefined : filterStatus,
        page,
        pageSize: 20,
      })

      setDocuments(response.data)
      setTotal(response.total)
    } catch (error) {
      console.error("Failed to load documents:", error)
      toast.error("Failed to load documents")
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async (documentId: string) => {
    if (!confirm("Are you sure you want to delete this document?")) return

    try {
      await apiClient.deleteDocument(documentId)
      toast.success("Document deleted")
      loadDocuments()
    } catch (error) {
      console.error("Delete failed:", error)
      toast.error("Failed to delete document")
    }
  }

  const getStatusBadge = (status: ExtractionStatus) => {
    const variants: Record<ExtractionStatus, { color: string; icon: any }> = {
      complete: { color: "bg-green-100 text-green-800", icon: CheckCircle },
      incomplete: { color: "bg-yellow-100 text-yellow-800", icon: AlertCircle },
      failed: { color: "bg-red-100 text-red-800", icon: AlertCircle },
      processing: { color: "bg-blue-100 text-blue-800", icon: Clock },
    }

    const { color, icon: Icon } = variants[status]

    return (
      <Badge className={`${color} flex items-center gap-1`}>
        <Icon className="w-3 h-3" />
        {status}
      </Badge>
    )
  }

  return (
    <div className="space-y-4">
      {/* Filters */}
      <Card className="p-4">
        <div className="flex gap-4 items-center">
          <div className="flex-1">
            <label className="text-sm font-medium mb-2 block">Document Type</label>
            <select
              value={filterType}
              onChange={(e) => {
                setFilterType(e.target.value as any)
                setPage(1)
              }}
              className="w-full px-3 py-2 border border-border rounded-lg bg-card"
            >
              {documentTypes.map((type) => (
                <option key={type.value} value={type.value}>
                  {type.label}
                </option>
              ))}
            </select>
          </div>

          <div className="flex-1">
            <label className="text-sm font-medium mb-2 block">Status</label>
            <select
              value={filterStatus}
              onChange={(e) => {
                setFilterStatus(e.target.value as any)
                setPage(1)
              }}
              className="w-full px-3 py-2 border border-border rounded-lg bg-card"
            >
              {statusOptions.map((status) => (
                <option key={status.value} value={status.value}>
                  {status.label}
                </option>
              ))}
            </select>
          </div>

          <div className="flex-1 flex items-end">
            <Button onClick={loadDocuments} variant="outline" className="w-full">
              Refresh
            </Button>
          </div>
        </div>
      </Card>

      {/* Documents List */}
      <Card>
        {loading ? (
          <div className="p-4 space-y-3">
            {[...Array(5)].map((_, i) => (
              <Skeleton key={i} className="h-16 w-full" />
            ))}
          </div>
        ) : documents.length === 0 ? (
          <div className="p-12 text-center">
            <FileText className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
            <h3 className="text-lg font-semibold mb-2">No documents found</h3>
            <p className="text-muted-foreground">Upload a document to get started</p>
          </div>
        ) : (
          <div className="divide-y">
            {documents.map((doc) => (
              <div key={doc.document_id} className="p-4 hover:bg-muted/50 transition-colors">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-4 flex-1">
                    <FileText className="w-8 h-8 text-primary" />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <h3 className="font-semibold truncate">
                          {(doc as any).document_name || doc.document_number || doc.document_id.substring(0, 8)}
                        </h3>
                        <Badge variant="outline">{doc.document_type}</Badge>
                        {getStatusBadge(doc.extraction_status)}
                      </div>
                      <div className="flex flex-col gap-1">
                        <div className="flex gap-4 text-sm text-muted-foreground">
                          <span>{doc.fields_count} fields</span>
                          <span>{doc.items_count} items</span>
                          <span>{format(new Date(doc.created_at), "MMM d, yyyy HH:mm")}</span>
                        </div>
                        {(doc as any).document_name && (doc as any).filename && (
                          <span className="text-xs text-muted-foreground">
                            File: {(doc as any).filename}
                          </span>
                        )}
                      </div>
                      {doc.missing_fields.length > 0 && (
                        <p className="text-xs text-yellow-600 mt-1">
                          Missing: {doc.missing_fields.join(", ")}
                        </p>
                      )}
                    </div>
                  </div>

                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => onViewDocument?.(doc)}
                    >
                      <Eye className="w-4 h-4" />
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => handleDelete(doc.document_id)}
                    >
                      <Trash2 className="w-4 h-4 text-destructive" />
                    </Button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Pagination */}
        {!loading && total > 20 && (
          <div className="p-4 border-t flex items-center justify-between">
            <p className="text-sm text-muted-foreground">
              Showing {(page - 1) * 20 + 1} to {Math.min(page * 20, total)} of {total} documents
            </p>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
              >
                Previous
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => p + 1)}
                disabled={page * 20 >= total}
              >
                Next
              </Button>
            </div>
          </div>
        )}
      </Card>
    </div>
  )
}
