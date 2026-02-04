"use client"

import { useState } from "react"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { FileText, X, ZoomIn, ZoomOut, Download, Printer as Print, ChevronLeft, ChevronRight } from "lucide-react"

interface DocumentData {
  id: string
  name: string
  type: "invoice" | "po" | "manifest" | "receipt"
  status: "validated" | "failed" | "pending"
  uploadedAt: string
  validationScore?: number
  content: DocumentContent
}

interface DocumentContent {
  header?: HeaderInfo
  items?: DocumentItem[]
  summary?: SummaryInfo
  metadata?: Record<string, any>
}

interface HeaderInfo {
  title: string
  documentNumber: string
  date: string
  issuer: string
  receiver?: string
}

interface DocumentItem {
  id: string
  description: string
  quantity: number
  unit: string
  unitPrice: number
  total: number
}

interface SummaryInfo {
  subtotal: number
  tax: number
  shipping?: number
  total: number
  currency: string
}

interface DocumentRendererProps {
  document: DocumentData
  onClose?: () => void
}

export default function DocumentRenderer({ document, onClose }: DocumentRendererProps) {
  const [zoom, setZoom] = useState(100)
  const [page, setPage] = useState(1)

  const handleZoom = (direction: "in" | "out") => {
    setZoom((prev) => {
      if (direction === "in" && prev < 200) return prev + 10
      if (direction === "out" && prev > 50) return prev - 10
      return prev
    })
  }

  const getTypeColor = (type: string) => {
    switch (type) {
      case "invoice":
        return "bg-blue-100 text-blue-700"
      case "po":
        return "bg-purple-100 text-purple-700"
      case "manifest":
        return "bg-green-100 text-green-700"
      case "receipt":
        return "bg-amber-100 text-amber-700"
      default:
        return "bg-gray-100 text-gray-700"
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case "validated":
        return "text-green-600"
      case "failed":
        return "text-destructive"
      case "pending":
        return "text-amber-600"
      default:
        return "text-foreground"
    }
  }

  const formatCurrency = (amount: number, currency = "USD") => {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency,
    }).format(amount)
  }

  return (
    <div className="flex flex-col h-screen bg-background">
      {/* Toolbar */}
      <div className="flex items-center justify-between gap-4 p-4 border-b border-border bg-card sticky top-0 z-10">
        <div className="flex items-center gap-4 flex-1">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-primary/10 rounded-lg">
              <FileText className="w-5 h-5 text-primary" />
            </div>
            <div className="min-w-0">
              <p className="font-semibold text-foreground truncate">{document.name}</p>
              <div className="flex items-center gap-2">
                <span className={`text-xs font-semibold px-2 py-1 rounded ${getTypeColor(document.type)}`}>
                  {document.type.toUpperCase()}
                </span>
                <span className={`text-xs font-semibold ${getStatusColor(document.status)}`}>
                  {document.status === "validated" && "✓ Validated"}
                  {document.status === "failed" && "✕ Failed"}
                  {document.status === "pending" && "⧗ Pending"}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Toolbar Actions */}
        <div className="flex items-center gap-2">
          <Button onClick={() => handleZoom("out")} variant="outline" size="sm" title="Zoom out">
            <ZoomOut className="w-4 h-4" />
          </Button>
          <span className="text-sm text-muted-foreground min-w-12 text-center">{zoom}%</span>
          <Button onClick={() => handleZoom("in")} variant="outline" size="sm" title="Zoom in">
            <ZoomIn className="w-4 h-4" />
          </Button>
          <Button variant="outline" size="sm" title="Print">
            <Print className="w-4 h-4" />
          </Button>
          <Button variant="outline" size="sm" title="Download">
            <Download className="w-4 h-4" />
          </Button>
          {onClose && (
            <Button onClick={onClose} variant="outline" size="sm" title="Close">
              <X className="w-4 h-4" />
            </Button>
          )}
        </div>
      </div>

      {/* Document View */}
      <div className="flex-1 overflow-auto p-4 flex justify-center">
        <div
          style={{ transform: `scale(${zoom / 100})`, transformOrigin: "top center" }}
          className="transition-transform duration-200"
        >
          <Card className="w-[800px] shadow-xl">
            {/* Header Section */}
            {document.content.header && (
              <div className="p-8 border-b border-border">
                <div className="grid grid-cols-3 gap-8 mb-8">
                  <div>
                    <p className="text-sm text-muted-foreground mb-1">Document Type</p>
                    <p className="text-lg font-bold text-foreground">{document.content.header.title}</p>
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground mb-1">Number</p>
                    <p className="text-lg font-bold text-foreground">{document.content.header.documentNumber}</p>
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground mb-1">Date</p>
                    <p className="text-lg font-bold text-foreground">{document.content.header.date}</p>
                  </div>
                </div>

                <div className="border-t border-border pt-6">
                  <div className="grid grid-cols-2 gap-8">
                    <div>
                      <p className="text-xs text-muted-foreground uppercase tracking-wide mb-2">From</p>
                      <p className="font-semibold text-foreground">{document.content.header.issuer}</p>
                    </div>
                    {document.content.header.receiver && (
                      <div>
                        <p className="text-xs text-muted-foreground uppercase tracking-wide mb-2">To</p>
                        <p className="font-semibold text-foreground">{document.content.header.receiver}</p>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* Items Table */}
            {document.content.items && document.content.items.length > 0 && (
              <div className="p-8 border-b border-border">
                <h3 className="text-sm font-semibold text-foreground uppercase tracking-wide mb-4">Line Items</h3>
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b border-border">
                        <th className="text-left text-xs font-semibold text-muted-foreground py-3 px-0">Description</th>
                        <th className="text-right text-xs font-semibold text-muted-foreground py-3 px-0">Qty</th>
                        <th className="text-right text-xs font-semibold text-muted-foreground py-3 px-0">Unit Price</th>
                        <th className="text-right text-xs font-semibold text-muted-foreground py-3 px-0">Total</th>
                      </tr>
                    </thead>
                    <tbody>
                      {document.content.items.map((item) => (
                        <tr key={item.id} className="border-b border-border">
                          <td className="text-sm text-foreground py-3 px-0">{item.description}</td>
                          <td className="text-sm text-foreground py-3 px-0 text-right">
                            {item.quantity} {item.unit}
                          </td>
                          <td className="text-sm text-foreground py-3 px-0 text-right">
                            {formatCurrency(item.unitPrice)}
                          </td>
                          <td className="text-sm text-foreground py-3 px-0 text-right">{formatCurrency(item.total)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Summary Section */}
            {document.content.summary && (
              <div className="p-8">
                <div className="ml-auto w-64">
                  <div className="flex justify-between py-2 mb-2">
                    <span className="text-sm text-foreground">Subtotal</span>
                    <span className="text-sm text-foreground">
                      {formatCurrency(document.content.summary.subtotal, document.content.summary.currency)}
                    </span>
                  </div>
                  <div className="flex justify-between py-2 mb-2">
                    <span className="text-sm text-foreground">Tax</span>
                    <span className="text-sm text-foreground">
                      {formatCurrency(document.content.summary.tax, document.content.summary.currency)}
                    </span>
                  </div>
                  {document.content.summary.shipping !== undefined && (
                    <div className="flex justify-between py-2 mb-2">
                      <span className="text-sm text-foreground">Shipping</span>
                      <span className="text-sm text-foreground">
                        {formatCurrency(document.content.summary.shipping, document.content.summary.currency)}
                      </span>
                    </div>
                  )}
                  <div className="flex justify-between py-4 px-4 bg-primary/10 rounded-lg mt-4 border border-primary/20">
                    <span className="font-semibold text-foreground">Total Due</span>
                    <span className="font-bold text-lg text-primary">
                      {formatCurrency(document.content.summary.total, document.content.summary.currency)}
                    </span>
                  </div>
                </div>
              </div>
            )}

            {/* Footer with metadata */}
            <div className="p-6 bg-muted border-t border-border">
              <div className="flex items-center justify-between text-xs text-muted-foreground">
                <span>{document.id}</span>
                <span>{document.uploadedAt}</span>
                {document.validationScore !== undefined && <span>Validation Score: {document.validationScore}%</span>}
              </div>
            </div>
          </Card>
        </div>
      </div>

      {/* Pagination (if needed for multi-page) */}
      <div className="flex items-center justify-center gap-4 p-4 border-t border-border bg-card">
        <Button variant="outline" size="sm">
          <ChevronLeft className="w-4 h-4" />
        </Button>
        <span className="text-sm text-muted-foreground">Page {page}</span>
        <Button variant="outline" size="sm">
          <ChevronRight className="w-4 h-4" />
        </Button>
      </div>
    </div>
  )
}
