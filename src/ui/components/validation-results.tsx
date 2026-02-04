"use client"

import { useState } from "react"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { CheckCircle, AlertCircle, XCircle, Download, Eye, ChevronDown } from "lucide-react"

export default function ValidationResults() {
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [filterStatus, setFilterStatus] = useState<"all" | "passed" | "failed" | "warning">("all")

  const mockResults = [
    {
      id: "doc-001",
      fileName: "Invoice_2024_001.pdf",
      documentType: "invoice",
      status: "passed",
      uploadedAt: "2024-01-15 10:30 AM",
      validationScore: 98,
      fields: {
        invoiceNumber: { value: "INV-2024-001", status: "valid" },
        date: { value: "2024-01-15", status: "valid" },
        amount: { value: "$5,234.50", status: "valid" },
        vendor: { value: "Acme Corp", status: "valid" },
        dueDate: { value: "2024-02-15", status: "valid" },
      },
      issues: [],
    },
    {
      id: "doc-002",
      fileName: "PO_12345.xlsx",
      documentType: "po",
      status: "warning",
      uploadedAt: "2024-01-15 11:00 AM",
      validationScore: 85,
      fields: {
        poNumber: { value: "PO-2024-12345", status: "valid" },
        date: { value: "2024-01-15", status: "valid" },
        amount: { value: "$12,500.00", status: "valid" },
        vendor: { value: "Unknown Vendor", status: "warning" },
        items: { value: "5 items", status: "valid" },
      },
      issues: ["Vendor not found in system", "Missing tax ID"],
    },
    {
      id: "doc-003",
      fileName: "Manifest_Jan_2024.pdf",
      documentType: "manifest",
      status: "passed",
      uploadedAt: "2024-01-15 02:15 PM",
      validationScore: 96,
      fields: {
        shipmentId: { value: "SHIP-2024-5678", status: "valid" },
        origin: { value: "Warehouse A", status: "valid" },
        destination: { value: "Customer Site", status: "valid" },
        itemCount: { value: "42 units", status: "valid" },
        weight: { value: "1,250 lbs", status: "valid" },
      },
      issues: [],
    },
    {
      id: "doc-004",
      fileName: "Receipt_incomplete.pdf",
      documentType: "receipt",
      status: "failed",
      uploadedAt: "2024-01-15 03:45 PM",
      validationScore: 42,
      fields: {
        receiptNumber: { value: "Missing", status: "error" },
        date: { value: "2024-01-10", status: "valid" },
        amount: { value: "Illegible", status: "error" },
        vendor: { value: "Unknown", status: "error" },
        signature: { value: "Missing", status: "error" },
      },
      issues: [
        "Receipt number not found",
        "Amount field is illegible",
        "Missing vendor information",
        "Missing signature",
      ],
    },
  ]

  const filteredResults = mockResults.filter((result) => {
    if (filterStatus === "all") return true
    return result.status === filterStatus
  })

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "passed":
        return <CheckCircle className="w-5 h-5 text-green-600" />
      case "warning":
        return <AlertCircle className="w-5 h-5 text-amber-600" />
      case "failed":
        return <XCircle className="w-5 h-5 text-destructive" />
      default:
        return null
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case "passed":
        return "bg-green-100 text-green-700"
      case "warning":
        return "bg-amber-100 text-amber-700"
      case "failed":
        return "bg-red-100 text-red-700"
      default:
        return "bg-gray-100 text-gray-700"
    }
  }

  const getScoreColor = (score: number) => {
    if (score >= 90) return "text-green-600"
    if (score >= 70) return "text-amber-600"
    return "text-destructive"
  }

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="mb-8">
        <h1 className="text-4xl font-bold text-foreground mb-2">Validation Results</h1>
        <p className="text-muted-foreground">Review the validation status and details of your uploaded documents.</p>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-4 gap-4 mb-8">
        <Card className="p-4">
          <p className="text-sm text-muted-foreground mb-1">Total Documents</p>
          <p className="text-2xl font-bold text-foreground">{mockResults.length}</p>
        </Card>
        <Card className="p-4">
          <p className="text-sm text-muted-foreground mb-1">Passed</p>
          <p className="text-2xl font-bold text-green-600">{mockResults.filter((r) => r.status === "passed").length}</p>
        </Card>
        <Card className="p-4">
          <p className="text-sm text-muted-foreground mb-1">Warnings</p>
          <p className="text-2xl font-bold text-amber-600">
            {mockResults.filter((r) => r.status === "warning").length}
          </p>
        </Card>
        <Card className="p-4">
          <p className="text-sm text-muted-foreground mb-1">Failed</p>
          <p className="text-2xl font-bold text-destructive">
            {mockResults.filter((r) => r.status === "failed").length}
          </p>
        </Card>
      </div>

      {/* Filters and Actions */}
      <div className="flex gap-4 mb-6">
        <div className="flex gap-2">
          {["all", "passed", "warning", "failed"].map((status) => (
            <button
              key={status}
              onClick={() => setFilterStatus(status as any)}
              className={`px-4 py-2 rounded-lg font-medium transition-colors capitalize ${
                filterStatus === status
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted text-foreground hover:bg-border"
              }`}
            >
              {status}
            </button>
          ))}
        </div>
        <div className="ml-auto flex gap-2">
          <Button variant="outline" className="flex items-center gap-2 bg-transparent">
            <Download className="w-4 h-4" />
            Export
          </Button>
        </div>
      </div>

      {/* Results List */}
      <div className="space-y-4">
        {filteredResults.map((result) => (
          <Card key={result.id} className="overflow-hidden hover:shadow-lg transition-shadow">
            {/* Result Header */}
            <button
              onClick={() => setExpandedId(expandedId === result.id ? null : result.id)}
              className="w-full p-6 flex items-center gap-4 hover:bg-muted/30 transition-colors text-left"
            >
              {getStatusIcon(result.status)}
              <div className="flex-1 min-w-0">
                <p className="font-semibold text-foreground truncate">{result.fileName}</p>
                <p className="text-sm text-muted-foreground">
                  {result.documentType.toUpperCase()} • {result.uploadedAt}
                </p>
              </div>
              <div className="flex items-center gap-4">
                <div className="text-right">
                  <p className={`text-lg font-bold ${getScoreColor(result.validationScore)}`}>
                    {result.validationScore}%
                  </p>
                  <p
                    className={`inline-block px-3 py-1 rounded-full text-xs font-semibold ${getStatusColor(result.status)}`}
                  >
                    {result.status.charAt(0).toUpperCase() + result.status.slice(1)}
                  </p>
                </div>
                <ChevronDown
                  className={`w-5 h-5 text-muted-foreground transition-transform ${
                    expandedId === result.id ? "transform rotate-180" : ""
                  }`}
                />
              </div>
            </button>

            {/* Expanded Details */}
            {expandedId === result.id && (
              <div className="border-t border-border px-6 py-6 bg-muted/30">
                {/* Extracted Fields */}
                <div className="mb-6">
                  <h4 className="font-semibold text-foreground mb-4">Extracted Fields</h4>
                  <div className="grid grid-cols-2 gap-4">
                    {Object.entries(result.fields).map(([key, field]: any) => (
                      <div key={key} className="p-3 bg-card rounded-lg border border-border">
                        <p className="text-xs text-muted-foreground uppercase tracking-wide mb-1">
                          {key.replace(/([A-Z])/g, " $1")}
                        </p>
                        <p className="font-medium text-foreground mb-2">{field.value}</p>
                        {field.status === "valid" && (
                          <span className="inline-block text-xs font-semibold text-green-600">✓ Valid</span>
                        )}
                        {field.status === "warning" && (
                          <span className="inline-block text-xs font-semibold text-amber-600">⚠ Warning</span>
                        )}
                        {field.status === "error" && (
                          <span className="inline-block text-xs font-semibold text-destructive">✕ Error</span>
                        )}
                      </div>
                    ))}
                  </div>
                </div>

                {/* Issues */}
                {result.issues.length > 0 && (
                  <div className="mb-6">
                    <h4 className="font-semibold text-foreground mb-3">Issues Found</h4>
                    <div className="space-y-2">
                      {result.issues.map((issue, i) => (
                        <div
                          key={i}
                          className="flex items-start gap-3 p-3 bg-red-50 dark:bg-red-900/20 rounded-lg border border-red-200 dark:border-red-800"
                        >
                          <AlertCircle className="w-4 h-4 text-destructive mt-0.5 flex-shrink-0" />
                          <p className="text-sm text-foreground">{issue}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Action Buttons */}
                <div className="flex gap-3">
                  <Button variant="outline" className="flex items-center gap-2 bg-transparent">
                    <Eye className="w-4 h-4" />
                    View Document
                  </Button>
                  {result.status !== "passed" && (
                    <Button className="bg-primary hover:bg-primary/90">Correct & Revalidate</Button>
                  )}
                  {result.status === "passed" && (
                    <Button className="bg-green-600 hover:bg-green-700 text-white">Proceed to Shipment</Button>
                  )}
                </div>
              </div>
            )}
          </Card>
        ))}
      </div>
    </div>
  )
}
