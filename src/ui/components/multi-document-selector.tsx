"use client"

import { useState, useEffect } from "react"
import { Checkbox } from "@/components/ui/checkbox"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Card } from "@/components/ui/card"
import { ScrollArea } from "@/components/ui/scroll-area"
import { FileText, Search, Layers } from "lucide-react"
import { apiClient, type DocumentResponse } from "@/lib/api-client"
import { Skeleton } from "@/components/ui/skeleton"

export interface SelectedDocument {
  document_id: string
  document_type: string
  document_number?: string
}

interface MultiDocumentSelectorProps {
  /** Currently selected document IDs */
  selectedDocumentIds: string[]
  /** Callback when selection changes */
  onSelectionChange: (documentIds: string[]) => void
  /** Optional: Filter to specific document types */
  allowedTypes?: string[]
  /** Optional: Minimum number of documents required */
  minDocuments?: number
  /** Optional: Maximum number of documents allowed */
  maxDocuments?: number
  /** Optional: Current document ID to exclude from selection */
  excludeDocumentId?: string
}

export default function MultiDocumentSelector({
  selectedDocumentIds,
  onSelectionChange,
  allowedTypes,
  minDocuments = 1,
  maxDocuments = 10,
  excludeDocumentId,
}: MultiDocumentSelectorProps) {
  const [documents, setDocuments] = useState<DocumentResponse[]>([])
  const [loading, setLoading] = useState(true)
  const [searchTerm, setSearchTerm] = useState("")

  useEffect(() => {
    loadDocuments()
  }, [allowedTypes, excludeDocumentId])

  const loadDocuments = async () => {
    setLoading(true)
    try {
      // Fetch documents from API
      const response = await apiClient.listDocuments({
        pageSize: 100,
        status: "complete",
      })

      let filteredDocs = response.data

      // Filter by allowed types if specified
      if (allowedTypes && allowedTypes.length > 0) {
        filteredDocs = filteredDocs.filter((doc) =>
          doc.document_type && allowedTypes.includes(doc.document_type)
        )
      }

      // Exclude specific document if specified
      if (excludeDocumentId) {
        filteredDocs = filteredDocs.filter(
          (doc) => doc.document_id !== excludeDocumentId
        )
      }

      setDocuments(filteredDocs)
    } catch (error) {
      console.error("Failed to load documents:", error)
    } finally {
      setLoading(false)
    }
  }

  const handleToggleDocument = (documentId: string) => {
    const isSelected = selectedDocumentIds.includes(documentId)

    if (isSelected) {
      // Remove from selection
      onSelectionChange(selectedDocumentIds.filter((id) => id !== documentId))
    } else {
      // Add to selection (if under max limit)
      if (selectedDocumentIds.length < maxDocuments) {
        onSelectionChange([...selectedDocumentIds, documentId])
      }
    }
  }

  const filteredDocuments = documents.filter((doc) => {
    const searchLower = searchTerm.toLowerCase()
    return (
      doc.document_id.toLowerCase().includes(searchLower) ||
      (doc.document_type?.toLowerCase().includes(searchLower) ?? false) ||
      doc.document_number?.toLowerCase().includes(searchLower)
    )
  })

  const getDocumentTypeColor = (type: string | null | undefined) => {
    if (!type) return "bg-gray-100 text-gray-700"
    const colors: Record<string, string> = {
      invoice: "bg-blue-100 text-blue-700",
      "packing-list": "bg-green-100 text-green-700",
      "bill-of-entry": "bg-purple-100 text-purple-700",
      coo: "bg-amber-100 text-amber-700",
      "freight-document": "bg-orange-100 text-orange-700",
    }
    return colors[type.toLowerCase()] || "bg-gray-100 text-gray-700"
  }

  if (loading) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-20 w-full" />
        <Skeleton className="h-20 w-full" />
        <Skeleton className="h-20 w-full" />
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Layers className="w-5 h-5 text-muted-foreground" />
          <div>
            <Label className="text-sm font-medium">Select Source Documents</Label>
            <p className="text-xs text-muted-foreground">
              Choose {minDocuments}-{maxDocuments} documents to combine
            </p>
          </div>
        </div>
        <Badge variant="secondary" className="text-xs">
          {selectedDocumentIds.length} / {maxDocuments} selected
        </Badge>
      </div>

      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-muted-foreground" />
        <Input
          placeholder="Search documents..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="pl-9"
        />
      </div>

      {/* Document List */}
      <ScrollArea className="h-[300px] border rounded-lg">
        <div className="p-2 space-y-2">
          {filteredDocuments.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-8 text-center">
              <FileText className="w-12 h-12 text-muted-foreground mb-2" />
              <p className="text-sm text-muted-foreground">No documents found</p>
            </div>
          ) : (
            filteredDocuments.map((doc) => {
              const isSelected = selectedDocumentIds.includes(doc.document_id)
              const isDisabled =
                !isSelected && selectedDocumentIds.length >= maxDocuments

              return (
                <Card
                  key={doc.document_id}
                  className={`p-3 cursor-pointer transition-colors ${
                    isSelected
                      ? "bg-primary/5 border-primary"
                      : "hover:bg-muted/50"
                  } ${isDisabled ? "opacity-50 cursor-not-allowed" : ""}`}
                  onClick={() => !isDisabled && handleToggleDocument(doc.document_id)}
                >
                  <div className="flex items-start gap-3">
                    <Checkbox
                      checked={isSelected}
                      disabled={isDisabled}
                      onCheckedChange={() => handleToggleDocument(doc.document_id)}
                      className="mt-1"
                    />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <p className="text-sm font-medium truncate">
                          {doc.document_number || doc.document_id.slice(0, 8)}
                        </p>
                        <Badge
                          variant="outline"
                          className={`text-xs ${getDocumentTypeColor(doc.document_type)}`}
                        >
                          {doc.document_type || "unknown"}
                        </Badge>
                      </div>
                      <div className="flex items-center gap-4 text-xs text-muted-foreground">
                        <span>{doc.fields_count} fields</span>
                        {doc.items_count > 0 && (
                          <span>{doc.items_count} items</span>
                        )}
                        {doc.extraction_confidence && (
                          <span>
                            {(doc.extraction_confidence * 100).toFixed(0)}% confidence
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                </Card>
              )
            })
          )}
        </div>
      </ScrollArea>

      {/* Validation Messages */}
      {selectedDocumentIds.length < minDocuments && (
        <p className="text-xs text-amber-600">
          Please select at least {minDocuments} document{minDocuments > 1 ? "s" : ""}
        </p>
      )}

      {selectedDocumentIds.length >= maxDocuments && (
        <p className="text-xs text-muted-foreground">
          Maximum {maxDocuments} documents reached
        </p>
      )}
    </div>
  )
}
