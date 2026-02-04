/**
 * Selected Document Banner Component
 * Shows selected document context during template selection
 */

"use client"

import { type DocumentResponse } from "@/lib/api-client"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { FileText, ArrowLeft, CheckCircle } from "lucide-react"
import { format } from "date-fns"

interface SelectedDocumentBannerProps {
  document: DocumentResponse
  onDeselect: () => void
}

export default function SelectedDocumentBanner({ document, onDeselect }: SelectedDocumentBannerProps) {
  // Status badge styling
  const getStatusBadgeClass = (status: string) => {
    switch (status) {
      case "complete":
        return "bg-green-100 text-green-800 border-green-300"
      case "processing":
        return "bg-blue-100 text-blue-800 border-blue-300"
      case "incomplete":
        return "bg-yellow-100 text-yellow-800 border-yellow-300"
      case "failed":
        return "bg-red-100 text-red-800 border-red-300"
      default:
        return ""
    }
  }

  return (
    <Card className="p-4 bg-primary/5 border-primary/20">
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-4 flex-1 min-w-0">
          {/* Icon */}
          <div className="flex-shrink-0">
            <div className="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center">
              <FileText className="w-6 h-6 text-primary" />
            </div>
          </div>

          {/* Document Info */}
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <h3 className="font-semibold truncate">
                {document.document_name || "Unnamed Document"}
              </h3>
              <Badge className={getStatusBadgeClass(document.extraction_status)}>
                <CheckCircle className="w-3 h-3 mr-1" />
                {document.extraction_status}
              </Badge>
            </div>

            <div className="flex items-center gap-4 text-sm text-muted-foreground">
              <span className="capitalize">{document.document_type || "Unknown type"}</span>
              <span>•</span>
              <span>{document.fields_count || 0} fields</span>
              <span>•</span>
              <span>{document.items_count || 0} items</span>
              {document.is_multi_page && (
                <>
                  <span>•</span>
                  <span>{document.total_pages} pages</span>
                </>
              )}
            </div>

            <div className="text-xs text-muted-foreground mt-1">
              Created {format(new Date(document.created_at), "MMM dd, yyyy 'at' HH:mm")}
            </div>
          </div>
        </div>

        {/* Change Document Button */}
        <Button variant="outline" onClick={onDeselect} className="flex-shrink-0">
          <ArrowLeft className="w-4 h-4 mr-2" />
          Change Document
        </Button>
      </div>
    </Card>
  )
}
