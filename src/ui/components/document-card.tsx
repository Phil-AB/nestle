/**
 * Document Card Component
 * Displays a document in a selectable card format with metadata
 */

"use client"

import { type DocumentResponse } from "@/lib/api-client"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { FileText, Calendar, CheckCircle, AlertCircle, Clock, XCircle } from "lucide-react"
import { format } from "date-fns"

interface DocumentCardProps {
  document: DocumentResponse
  onSelect: () => void
  selected?: boolean
  compact?: boolean
}

export default function DocumentCard({ document, onSelect, selected = false, compact = false }: DocumentCardProps) {
  // Status badge styling
  const getStatusConfig = (status: string) => {
    switch (status) {
      case "complete":
        return {
          icon: CheckCircle,
          variant: "default" as const,
          className: "bg-green-100 text-green-800 border-green-300",
        }
      case "processing":
        return {
          icon: Clock,
          variant: "secondary" as const,
          className: "bg-blue-100 text-blue-800 border-blue-300",
        }
      case "incomplete":
        return {
          icon: AlertCircle,
          variant: "secondary" as const,
          className: "bg-yellow-100 text-yellow-800 border-yellow-300",
        }
      case "failed":
        return {
          icon: XCircle,
          variant: "destructive" as const,
          className: "bg-red-100 text-red-800 border-red-300",
        }
      default:
        return {
          icon: FileText,
          variant: "outline" as const,
          className: "",
        }
    }
  }

  const statusConfig = getStatusConfig(document.extraction_status)
  const StatusIcon = statusConfig.icon

  return (
    <Card
      className={`
        transition-all cursor-pointer hover:shadow-lg
        ${selected ? "ring-2 ring-primary border-primary" : ""}
        ${compact ? "p-2" : ""}
      `}
      onClick={onSelect}
    >
      <CardHeader className={compact ? "p-3" : ""}>
        <div className="flex items-start justify-between gap-2">
          <div className="flex-1 min-w-0">
            <CardTitle className={`${compact ? "text-base" : "text-lg"} truncate`}>
              {document.document_name || "Unnamed Document"}
            </CardTitle>
            <p className="text-sm text-muted-foreground mt-1 capitalize">
              {document.document_type || "Unknown type"}
            </p>
          </div>
          <Badge className={statusConfig.className}>
            <StatusIcon className="w-3 h-3 mr-1" />
            {document.extraction_status}
          </Badge>
        </div>
      </CardHeader>

      {!compact && (
        <CardContent className="space-y-3">
          {/* Metadata */}
          <div className="flex items-center gap-4 text-sm text-muted-foreground">
            <div className="flex items-center gap-1">
              <FileText className="w-4 h-4" />
              <span>
                {document.fields_count || 0} fields • {document.items_count || 0} items
              </span>
            </div>
          </div>

          {/* Created date */}
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Calendar className="w-3 h-3" />
            <span>Created {format(new Date(document.created_at), "MMM dd, yyyy")}</span>
          </div>

          {/* Multi-page indicator */}
          {document.is_multi_page && (
            <Badge variant="outline" className="text-xs">
              {document.total_pages} pages
            </Badge>
          )}

          {/* Select button */}
          <Button
            variant={selected ? "default" : "outline"}
            className="w-full mt-4"
            onClick={(e) => {
              e.stopPropagation()
              onSelect()
            }}
          >
            {selected ? (
              <>
                <CheckCircle className="w-4 h-4 mr-2" />
                Selected
              </>
            ) : (
              "Select Document"
            )}
          </Button>
        </CardContent>
      )}
    </Card>
  )
}
