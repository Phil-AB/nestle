"use client"

import { useState } from "react"
import { Target, Save, Search, CheckCircle2, AlertCircle } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select"
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"

export default function GroundTruthEntry() {
    const [documentId, setDocumentId] = useState("")
    const [documentType, setDocumentType] = useState("")
    const [verifiedData, setVerifiedData] = useState("{}")
    const [verifiedBy, setVerifiedBy] = useState("")
    const [notes, setNotes] = useState("")
    const [loading, setLoading] = useState(false)
    const [status, setStatus] = useState<"idle" | "success" | "error">("idle")
    const [message, setMessage] = useState("")

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault()
        setLoading(true)
        setStatus("idle")

        try {
            // Parse JSON to validate
            const parsedData = JSON.parse(verifiedData)

            const response = await fetch("/api/ground-truth", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    document_id: documentId || null,
                    document_type: documentType,
                    verified_data: parsedData,
                    verified_by: verifiedBy,
                    notes: notes || null,
                }),
            })

            if (response.ok) {
                setStatus("success")
                setMessage("Ground truth saved successfully!")
                // Reset form
                setDocumentId("")
                setVerifiedData("{}")
                setNotes("")
            } else {
                const error = await response.json()
                setStatus("error")
                setMessage(error.detail || "Failed to save ground truth")
            }
        } catch (error) {
            setStatus("error")
            setMessage(error instanceof Error ? error.message : "Invalid JSON format")
        } finally {
            setLoading(false)
        }
    }

    return (
        <div className="p-8 max-w-4xl mx-auto space-y-6">
            {/* Header */}
            <div className="space-y-2">
                <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-lg bg-primary flex items-center justify-center">
                        <Target className="w-6 h-6 text-primary-foreground" />
                    </div>
                    <div>
                        <h1 className="text-3xl font-bold">Ground Truth Entry</h1>
                        <p className="text-muted-foreground">
                            Enter manually verified data for accuracy validation
                        </p>
                    </div>
                </div>
            </div>

            {/* Info Card */}
            <Card className="border-blue-200 bg-blue-50 dark:bg-blue-950 dark:border-blue-800">
                <CardContent className="pt-6">
                    <div className="flex gap-3">
                        <AlertCircle className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
                        <div className="text-sm text-blue-900 dark:text-blue-100">
                            <p className="font-medium mb-1">What is Ground Truth?</p>
                            <p>
                                Ground truth is the manually verified, correct data used to measure extraction accuracy.
                                The system will automatically compare extracted values against ground truth during validation.
                            </p>
                        </div>
                    </div>
                </CardContent>
            </Card>

            {/* Form */}
            <Card>
                <CardHeader>
                    <CardTitle>Enter Verified Data</CardTitle>
                    <CardDescription>
                        Provide the correct field values that were manually verified
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    <form onSubmit={handleSubmit} className="space-y-6">
                        {/* Document Type */}
                        <div className="space-y-2">
                            <Label htmlFor="documentType">
                                Document Type <span className="text-destructive">*</span>
                            </Label>
                            <Select value={documentType} onValueChange={setDocumentType} required>
                                <SelectTrigger id="documentType">
                                    <SelectValue placeholder="Select document type" />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="invoice">Invoice</SelectItem>
                                    <SelectItem value="packing_list">Packing List</SelectItem>
                                    <SelectItem value="bill_of_entry">Bill of Entry</SelectItem>
                                    <SelectItem value="certificate_of_origin">Certificate of Origin</SelectItem>
                                    <SelectItem value="freight_invoice">Freight Invoice</SelectItem>
                                </SelectContent>
                            </Select>
                        </div>

                        {/* Document ID (Optional) */}
                        <div className="space-y-2">
                            <Label htmlFor="documentId">
                                Document ID <span className="text-muted-foreground text-xs">(Optional)</span>
                            </Label>
                            <div className="flex gap-2">
                                <Input
                                    id="documentId"
                                    type="text"
                                    placeholder="e.g., 3fa85f64-5717-4562-b3fc-2c963f66afa6"
                                    value={documentId}
                                    onChange={(e) => setDocumentId(e.target.value)}
                                    className="font-mono text-sm"
                                />
                                <Button type="button" variant="outline" size="icon">
                                    <Search className="w-4 h-4" />
                                </Button>
                            </div>
                            <p className="text-xs text-muted-foreground">
                                Link to an existing extracted document (UUID)
                            </p>
                        </div>

                        {/* Verified By */}
                        <div className="space-y-2">
                            <Label htmlFor="verifiedBy">
                                Verified By <span className="text-destructive">*</span>
                            </Label>
                            <Input
                                id="verifiedBy"
                                type="text"
                                placeholder="e.g., john.doe@company.com"
                                value={verifiedBy}
                                onChange={(e) => setVerifiedBy(e.target.value)}
                                required
                            />
                        </div>

                        {/* Verified Data (JSON) */}
                        <div className="space-y-2">
                            <Label htmlFor="verifiedData">
                                Verified Field Values (JSON) <span className="text-destructive">*</span>
                            </Label>
                            <Textarea
                                id="verifiedData"
                                placeholder={`{
  "invoice_number": "INV-12345",
  "total_amount": 15000.00,
  "supplier_name": "ACME Corp",
  "date": "2024-01-15"
}`}
                                value={verifiedData}
                                onChange={(e) => setVerifiedData(e.target.value)}
                                className="font-mono text-sm min-h-[200px]"
                                required
                            />
                            <p className="text-xs text-muted-foreground">
                                Enter the correct field values in JSON format
                            </p>
                        </div>

                        {/* Notes */}
                        <div className="space-y-2">
                            <Label htmlFor="notes">
                                Notes <span className="text-muted-foreground text-xs">(Optional)</span>
                            </Label>
                            <Textarea
                                id="notes"
                                placeholder="Additional verification notes or comments..."
                                value={notes}
                                onChange={(e) => setNotes(e.target.value)}
                                rows={3}
                            />
                        </div>

                        {/* Status Message */}
                        {status !== "idle" && (
                            <div
                                className={`flex items-center gap-2 p-4 rounded-lg ${status === "success"
                                        ? "bg-green-50 dark:bg-green-950 text-green-900 dark:text-green-100 border border-green-200 dark:border-green-800"
                                        : "bg-red-50 dark:bg-red-950 text-red-900 dark:text-red-100 border border-red-200 dark:border-red-800"
                                    }`}
                            >
                                {status === "success" ? (
                                    <CheckCircle2 className="w-5 h-5" />
                                ) : (
                                    <AlertCircle className="w-5 h-5" />
                                )}
                                <p className="text-sm font-medium">{message}</p>
                            </div>
                        )}

                        {/* Submit Button */}
                        <div className="flex justify-end gap-3 pt-4">
                            <Button
                                type="button"
                                variant="outline"
                                onClick={() => {
                                    setDocumentId("")
                                    setVerifiedData("{}")
                                    setNotes("")
                                    setStatus("idle")
                                }}
                            >
                                Clear
                            </Button>
                            <Button type="submit" disabled={loading} className="gap-2">
                                <Save className="w-4 h-4" />
                                {loading ? "Saving..." : "Save Ground Truth"}
                            </Button>
                        </div>
                    </form>
                </CardContent>
            </Card>

            {/* Example Card */}
            <Card>
                <CardHeader>
                    <CardTitle className="text-lg">Example Ground Truth Entry</CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="space-y-4">
                        <div>
                            <div className="flex items-center gap-2 mb-2">
                                <Badge variant="outline">Invoice</Badge>
                                <span className="text-sm text-muted-foreground">→</span>
                                <span className="text-sm font-mono">DOC-UUID-123</span>
                            </div>
                            <pre className="bg-muted p-4 rounded-lg text-sm overflow-x-auto">
                                {`{
  "invoice_number": "INV-2024-001",
  "supplier_name": "ACME Corporation",
  "total_amount": 15000.00,
  "currency": "USD",
  "date": "2024-01-15",
  "po_number": "PO-8888"
}`}
                            </pre>
                        </div>
                    </div>
                </CardContent>
            </Card>
        </div>
    )
}
