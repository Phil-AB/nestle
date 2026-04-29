"use client"

import { useRef, useState } from "react"
import { useParams, useRouter } from "next/navigation"
import { useQuery } from "@tanstack/react-query"
import { apiClient, type ShipmentDetail, type ShipmentDocumentSummary, type ShipmentTokenUsageSummary, type DocumentResponse, type BundleValidationResponse, type BundleSegmentMeta } from "@/lib/api-client"
import { Card } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  ArrowLeft,
  Package,
  FileText,
  CheckCircle2,
  AlertTriangle,
  Clock,
  Loader2,
  ChevronDown,
  ChevronUp,
  Ship,
  FileStack,
  Cpu,
  Eye,
  FileImage,
  Upload,
  Files,
  Layers,
} from "lucide-react"
import { formatDistanceToNow } from "date-fns"
import Link from "next/link"

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const BRAND = "#63513D"
const BRAND_LIGHT = "#8B7355"

const DOC_TYPE_LABELS: Record<string, string> = {
  invoice: "Invoice",
  packing_list: "Packing List",
  bill_of_lading: "Bill of Lading",
  bill_of_entry: "Bill of Entry",
  airway_bill: "Airway Bill",
  certificate_of_origin: "Certificate of Origin",
  freight_manifest: "Freight Manifest",
}

const VALIDATION_TYPE_LABELS: Record<string, string> = {
  vendor_validation: "Step 2 — Vendor Docs",
  boe_validation: "Step 6 — BOE Cross-check",
}

// ---------------------------------------------------------------------------
// Status helpers
// ---------------------------------------------------------------------------

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, { cls: string; icon: React.ReactNode }> = {
    validated: { cls: "bg-green-100 text-green-700", icon: <CheckCircle2 className="w-3.5 h-3.5" /> },
    errors: { cls: "bg-red-100 text-red-700", icon: <AlertTriangle className="w-3.5 h-3.5" /> },
    pending: { cls: "bg-amber-100 text-amber-700", icon: <Clock className="w-3.5 h-3.5" /> },
  }
  const v = map[status] ?? { cls: "bg-muted text-muted-foreground", icon: null }
  return (
    <span className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-semibold capitalize ${v.cls}`}>
      {v.icon}
      {status}
    </span>
  )
}

function ExtractionStatusIcon({ status }: { status: string }) {
  if (status === "complete") return <CheckCircle2 className="w-4 h-4 text-green-600 flex-shrink-0" />
  if (status === "failed") return <AlertTriangle className="w-4 h-4 text-destructive flex-shrink-0" />
  return <Clock className="w-4 h-4 text-amber-500 flex-shrink-0" />
}

// ---------------------------------------------------------------------------
// Source document iframe viewer
// ---------------------------------------------------------------------------

function SourceDocumentViewer({ documentId, mimeType }: { documentId: string; mimeType?: string | null }) {
  const fileUrl = apiClient.getDocumentFileUrl(documentId)
  const isPdf = !mimeType || mimeType.includes("pdf")

  if (isPdf) {
    return (
      <div className="w-full rounded-lg overflow-hidden border border-border/60" style={{ height: 600 }}>
        <iframe src={fileUrl} className="w-full h-full" title="Source document" />
      </div>
    )
  }

  return (
    <div className="flex justify-center p-4 bg-muted/30 rounded-lg border border-border/60">
      <img
        src={fileUrl}
        alt="Source document"
        className="max-w-full max-h-[600px] object-contain rounded"
        onError={e => {
          (e.target as HTMLImageElement).style.display = "none"
        }}
      />
    </div>
  )
}

// ---------------------------------------------------------------------------
// Extracted fields display
// ---------------------------------------------------------------------------

function FieldValue({ value }: { value: any }) {
  if (value === null || value === undefined || value === "") {
    return <span className="text-muted-foreground italic text-xs">—</span>
  }
  if (typeof value === "object" && "value" in value) {
    const v = value.value
    const conf = value.confidence
    return (
      <span className="flex items-center gap-2">
        <span>{String(v ?? "—")}</span>
        {conf != null && (
          <span className="text-xs text-muted-foreground">({Math.round(conf * 100)}%)</span>
        )}
      </span>
    )
  }
  if (typeof value === "object") return <span className="text-xs font-mono">{JSON.stringify(value)}</span>
  return <span>{String(value)}</span>
}

function ExtractedFieldsPanel({ doc }: { doc: DocumentResponse }) {
  const fields = doc.fields ?? {}
  const items = doc.items ?? []
  const fieldEntries = Object.entries(fields).filter(([k]) => !k.startsWith("_"))

  return (
    <div className="space-y-6">
      {fieldEntries.length > 0 && (
        <div>
          <h4 className="text-sm font-semibold text-foreground mb-3">Extracted Fields</h4>
          <div className="divide-y divide-border/40 rounded-lg border border-border/60 overflow-hidden">
            {fieldEntries.map(([key, val]) => (
              <div key={key} className="grid grid-cols-[200px_1fr] gap-4 px-4 py-2.5 text-sm hover:bg-muted/20">
                <span className="text-muted-foreground capitalize truncate">
                  {key.replace(/_/g, " ")}
                </span>
                <span className="text-foreground font-medium break-words">
                  <FieldValue value={val} />
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {items.length > 0 && (
        <div>
          <h4 className="text-sm font-semibold text-foreground mb-3">
            Line Items ({items.length})
          </h4>
          <div className="overflow-x-auto rounded-lg border border-border/60">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border bg-muted/50">
                  <th className="text-left px-3 py-2 text-muted-foreground font-medium">#</th>
                  {Object.keys(items[0] ?? {})
                    .filter(k => !["column_index","column_number","row_index","table_block_index","table_bbox","normalized_header","original_header","original_page"].includes(k) && !k.startsWith("_"))
                    .map(k => (
                      <th key={k} className="text-left px-3 py-2 text-muted-foreground font-medium capitalize">
                        {k.replace(/_/g, " ")}
                      </th>
                    ))}
                </tr>
              </thead>
              <tbody>
                {items.map((item, idx) => (
                  <tr key={idx} className="border-b border-border/40 hover:bg-muted/20">
                    <td className="px-3 py-2 text-muted-foreground">{idx + 1}</td>
                    {Object.entries(item)
                      .filter(([k]) => !["column_index","column_number","row_index","table_block_index","table_bbox","normalized_header","original_header","original_page"].includes(k) && !k.startsWith("_"))
                      .map(([k, v]) => (
                        <td key={k} className="px-3 py-2">
                          <FieldValue value={v} />
                        </td>
                      ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {fieldEntries.length === 0 && items.length === 0 && (
        <p className="text-sm text-muted-foreground text-center py-8">No extracted data available.</p>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Expandable document card with inline content
// ---------------------------------------------------------------------------

function DocumentSection({ doc }: { doc: ShipmentDocumentSummary }) {
  const [open, setOpen] = useState(false)
  const [activeTab, setActiveTab] = useState("fields")

  const { data: fullDoc, isLoading } = useQuery<DocumentResponse>({
    queryKey: ["document", doc.document_id],
    queryFn: () => apiClient.getDocument(doc.document_id),
    enabled: open,
    staleTime: 60_000,
  })

  const label = DOC_TYPE_LABELS[doc.document_type] ?? doc.document_type.replace(/_/g, " ")

  return (
    <div className="rounded-xl border border-border/60 overflow-hidden">
      {/* Header row — click to expand */}
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center gap-4 px-5 py-4 hover:bg-muted/30 transition-colors text-left"
      >
        <div className="p-2 rounded-lg bg-muted flex-shrink-0">
          <FileText className="w-4 h-4 text-muted-foreground" />
        </div>

        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-foreground">{label}</p>
          <div className="flex items-center gap-3 mt-0.5 flex-wrap">
            <ExtractionStatusIcon status={doc.extraction_status} />
            <span className="text-xs text-muted-foreground capitalize">{doc.extraction_status}</span>
            {doc.fields_count > 0 && (
              <span className="text-xs text-muted-foreground">{doc.fields_count} fields</span>
            )}
            {doc.items_count > 0 && (
              <span className="text-xs text-muted-foreground">{doc.items_count} line items</span>
            )}
            {doc.extraction_confidence != null && (
              <span className="text-xs text-muted-foreground">
                {(doc.extraction_confidence * 100).toFixed(0)}% confidence
              </span>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2 flex-shrink-0">
          <Link
            href={`/documents/${doc.document_id}`}
            onClick={e => e.stopPropagation()}
            className="hidden sm:inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
          >
            <Eye className="w-3.5 h-3.5" />
            Full view
          </Link>
          {open ? (
            <ChevronUp className="w-4 h-4 text-muted-foreground" />
          ) : (
            <ChevronDown className="w-4 h-4 text-muted-foreground" />
          )}
        </div>
      </button>

      {/* Expanded content */}
      {open && (
        <div className="border-t border-border px-5 py-5 bg-muted/10">
          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
            </div>
          ) : !fullDoc ? (
            <p className="text-sm text-muted-foreground text-center py-8">Failed to load document.</p>
          ) : (
            <Tabs value={activeTab} onValueChange={setActiveTab}>
              <TabsList className="mb-5">
                <TabsTrigger value="fields" className="flex items-center gap-1.5">
                  <FileText className="w-3.5 h-3.5" />
                  Extracted Data
                </TabsTrigger>
                <TabsTrigger value="source" className="flex items-center gap-1.5">
                  <FileImage className="w-3.5 h-3.5" />
                  Source Document
                </TabsTrigger>
              </TabsList>

              <TabsContent value="fields">
                <ExtractedFieldsPanel doc={fullDoc} />
              </TabsContent>

              <TabsContent value="source">
                <SourceDocumentViewer
                  documentId={doc.document_id}
                  mimeType={fullDoc.mime_type}
                />
              </TabsContent>
            </Tabs>
          )}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Token usage card
// ---------------------------------------------------------------------------

function TokenUsageCard({ usage }: { usage: ShipmentTokenUsageSummary }) {
  const label = VALIDATION_TYPE_LABELS[usage.validation_type] ?? usage.validation_type
  return (
    <div className="p-4 rounded-lg border border-border/60 bg-muted/20">
      <p className="text-sm font-semibold text-foreground mb-3">{label}</p>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: "Total tokens", val: usage.total_tokens.toLocaleString() },
          { label: "Input", val: usage.input_tokens.toLocaleString() },
          { label: "Output", val: usage.output_tokens.toLocaleString() },
          { label: "Est. cost", val: `$${usage.estimated_cost_usd.toFixed(4)}` },
        ].map(c => (
          <div key={c.label}>
            <p className="text-xs text-muted-foreground">{c.label}</p>
            <p className="text-sm font-mono font-medium">{c.val}</p>
          </div>
        ))}
      </div>
      {usage.by_model.length > 0 && (
        <div className="mt-3 pt-3 border-t border-border/40 space-y-1">
          {usage.by_model.map((m, i) => (
            <div key={i} className="flex items-center justify-between text-xs text-muted-foreground">
              <span>{m.model}</span>
              <span>{m.total_tokens.toLocaleString()} tokens · {m.calls} calls</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Bundle upload panel
// ---------------------------------------------------------------------------

const DOC_TYPE_COLORS: Record<string, string> = {
  invoice: "bg-blue-50 text-blue-700 border-blue-200",
  packing_list: "bg-purple-50 text-purple-700 border-purple-200",
  bill_of_lading: "bg-teal-50 text-teal-700 border-teal-200",
  certificate_of_origin: "bg-green-50 text-green-700 border-green-200",
  sanitary_certificate: "bg-orange-50 text-orange-700 border-orange-200",
  certificate_of_analysis: "bg-pink-50 text-pink-700 border-pink-200",
  freight_manifest: "bg-indigo-50 text-indigo-700 border-indigo-200",
}

function SegmentBadge({ seg }: { seg: BundleSegmentMeta }) {
  const cls = DOC_TYPE_COLORS[seg.document_type] ?? "bg-muted text-muted-foreground border-border"
  const label = seg.document_type.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase())
  return (
    <div className={`flex items-center justify-between px-3 py-2 rounded-lg border text-sm ${cls}`}>
      <span className="font-medium">{label}</span>
      <div className="flex items-center gap-3 text-xs opacity-80">
        <span>p{seg.pages[0]}–{seg.pages[seg.pages.length - 1]}</span>
        <span>{Math.round(seg.confidence * 100)}% conf.</span>
      </div>
    </div>
  )
}

function BundleUploadPanel({ shipmentId, onComplete }: { shipmentId: string; onComplete?: () => void }) {
  const [open, setOpen] = useState(false)
  const [file, setFile] = useState<File | null>(null)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<BundleValidationResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  async function handleSubmit() {
    if (!file) return
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const res = await apiClient.validateBundle(shipmentId, file)
      setResult(res)
      onComplete?.()
    } catch (e: any) {
      setError(e.message ?? "Bundle validation failed")
    } finally {
      setLoading(false)
    }
  }

  const statusColor = result?.final_status === "passed"
    ? "text-green-700 bg-green-50"
    : result?.final_status === "requires_attention"
      ? "text-amber-700 bg-amber-50"
      : "text-red-700 bg-red-50"

  return (
    <Card className="border-border/60 overflow-hidden">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center gap-3 px-6 py-4 hover:bg-muted/30 transition-colors text-left"
      >
        <div className="p-1.5 rounded-lg bg-muted">
          <Layers className="w-4 h-4 text-muted-foreground" />
        </div>
        <div className="flex-1">
          <p className="text-sm font-semibold text-foreground">Upload Bundle PDF</p>
          <p className="text-xs text-muted-foreground mt-0.5">
            All documents combined in one file — invoice, BOL, packing list, COO, COA, sanitary cert
          </p>
        </div>
        {open ? <ChevronUp className="w-4 h-4 text-muted-foreground flex-shrink-0" /> : <ChevronDown className="w-4 h-4 text-muted-foreground flex-shrink-0" />}
      </button>

      {open && (
        <div className="border-t border-border px-6 py-5 space-y-5">
          {/* File picker */}
          <div
            onClick={() => inputRef.current?.click()}
            className="flex flex-col items-center justify-center gap-2 p-8 border-2 border-dashed border-border/60 rounded-xl cursor-pointer hover:bg-muted/20 transition-colors"
          >
            <Files className="w-8 h-8 text-muted-foreground" />
            {file ? (
              <p className="text-sm font-medium text-foreground">{file.name}</p>
            ) : (
              <p className="text-sm text-muted-foreground">Click to select a bundled PDF</p>
            )}
            <p className="text-xs text-muted-foreground">PDF only</p>
            <input
              ref={inputRef}
              type="file"
              accept=".pdf,application/pdf"
              className="hidden"
              onChange={e => setFile(e.target.files?.[0] ?? null)}
            />
          </div>

          <Button
            onClick={handleSubmit}
            disabled={!file || loading}
            className="w-full"
            style={{ background: BRAND }}
          >
            {loading ? (
              <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Segmenting &amp; validating…</>
            ) : (
              <><Upload className="w-4 h-4 mr-2" />Validate Bundle</>
            )}
          </Button>

          {error && (
            <div className="flex items-start gap-2 p-3 rounded-lg bg-red-50 border border-red-200">
              <AlertTriangle className="w-4 h-4 text-red-600 flex-shrink-0 mt-0.5" />
              <p className="text-sm text-red-700">{error}</p>
            </div>
          )}

          {result && (
            <div className="space-y-4">
              {/* Status */}
              <div className={`flex items-center gap-2 px-4 py-3 rounded-lg text-sm font-semibold ${statusColor}`}>
                {result.final_status === "passed"
                  ? <CheckCircle2 className="w-4 h-4" />
                  : <AlertTriangle className="w-4 h-4" />}
                {result.final_status?.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase())}
              </div>

              {/* Detected segments */}
              {result.bundle_segments && result.bundle_segments.length > 0 && (
                <div>
                  <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">
                    Detected segments ({result.bundle_segments.length})
                  </p>
                  <div className="space-y-1.5">
                    {result.bundle_segments.map((seg, i) => (
                      <SegmentBadge key={i} seg={seg} />
                    ))}
                  </div>
                </div>
              )}

              {/* Merged docs note */}
              {result.merged_documents && Object.keys(result.merged_documents).length > 0 && (
                <div className="text-xs text-muted-foreground bg-muted/40 rounded-lg px-3 py-2 space-y-0.5">
                  {Object.entries(result.merged_documents).map(([type, info]) => (
                    <p key={type}>
                      <span className="font-medium capitalize">{type.replace(/_/g, " ")}</span>
                      {" — merged "}{info.merged_count} documents
                      {info.merged_from.length > 0 && ` (${info.merged_from.join(", ")})`}
                    </p>
                  ))}
                </div>
              )}

              {/* Summary */}
              {result.summary && (
                <div className="grid grid-cols-3 gap-3">
                  {[
                    { label: "Checks", val: result.summary.total_checks ?? 0 },
                    { label: "Passed", val: result.summary.passed_checks ?? 0 },
                    { label: "Discrepancies", val: result.summary.total_discrepancies ?? 0 },
                  ].map(c => (
                    <div key={c.label} className="text-center p-3 bg-muted/30 rounded-lg">
                      <p className="text-lg font-bold">{c.val}</p>
                      <p className="text-xs text-muted-foreground">{c.label}</p>
                    </div>
                  ))}
                </div>
              )}

              {/* Discrepancies */}
              {result.discrepancies && result.discrepancies.length > 0 && (
                <div>
                  <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">
                    Discrepancies
                  </p>
                  <div className="space-y-2">
                    {result.discrepancies.map((d: any, i: number) => (
                      <div key={i} className="px-3 py-2 rounded-lg bg-amber-50 border border-amber-200 text-sm">
                        <p className="font-medium text-amber-800">{d.field ?? d.validator ?? "Issue"}</p>
                        <p className="text-amber-700 text-xs mt-0.5">{d.message ?? d.description ?? JSON.stringify(d)}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </Card>
  )
}

// ---------------------------------------------------------------------------
// Section wrapper
// ---------------------------------------------------------------------------

function Section({
  icon,
  title,
  count,
  iconBg,
  iconColor,
  children,
  emptyMessage,
  emptyAction,
}: {
  icon: React.ReactNode
  title: string
  count: number
  iconBg: string
  iconColor: string
  children: React.ReactNode
  emptyMessage: string
  emptyAction?: React.ReactNode
}) {
  return (
    <Card className="border-border/60 overflow-hidden">
      <div className="flex items-center gap-3 px-6 py-4 border-b border-border">
        <div className="p-1.5 rounded-lg" style={{ background: iconBg, color: iconColor }}>
          {icon}
        </div>
        <h2 className="text-base font-semibold text-foreground">{title}</h2>
        <Badge variant="secondary" className="ml-auto text-xs">
          {count} document{count !== 1 ? "s" : ""}
        </Badge>
      </div>
      <div className="p-5">
        {count === 0 ? (
          <div className="text-center py-6 space-y-3">
            <p className="text-sm text-muted-foreground">{emptyMessage}</p>
            {emptyAction}
          </div>
        ) : (
          <div className="space-y-3">{children}</div>
        )}
      </div>
    </Card>
  )
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function ShipmentDetailPage() {
  const params = useParams()
  const router = useRouter()
  const shipmentId = params.id as string

  const { data: shipment, isLoading, error } = useQuery<ShipmentDetail>({
    queryKey: ["shipment", shipmentId],
    queryFn: () => apiClient.getShipment(shipmentId),
    staleTime: 30_000,
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (error || !shipment) {
    return (
      <div className="p-8 max-w-4xl mx-auto">
        <Button onClick={() => router.back()} variant="outline" className="mb-6">
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back
        </Button>
        <Card className="p-12 text-center">
          <AlertTriangle className="w-12 h-12 text-destructive mx-auto mb-4" />
          <h2 className="text-xl font-bold mb-2">Shipment Not Found</h2>
          <p className="text-muted-foreground">
            {error instanceof Error ? error.message : "This shipment could not be loaded."}
          </p>
        </Card>
      </div>
    )
  }

  const vendorDocs = shipment.documents.filter(d => d.document_type !== "bill_of_entry")
  const boeDocs = shipment.documents.filter(d => d.document_type === "bill_of_entry")

  return (
    <div className="p-8 max-w-5xl mx-auto space-y-6">
      <Button onClick={() => router.back()} variant="outline" size="sm">
        <ArrowLeft className="w-4 h-4 mr-2" />
        Back
      </Button>

      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-4">
          <div className="p-3 rounded-xl" style={{ background: `${BRAND}18`, color: BRAND }}>
            <Package className="w-7 h-7" />
          </div>
          <div>
            <h1 className="text-2xl font-bold font-mono tracking-tight text-foreground">
              {shipment.shipment_number}
            </h1>
            {shipment.created_at && (
              <p className="text-sm text-muted-foreground mt-0.5">
                Created {formatDistanceToNow(new Date(shipment.created_at), { addSuffix: true })}
              </p>
            )}
          </div>
        </div>
        <StatusBadge status={shipment.status} />
      </div>

      {/* Metadata */}
      <Card className="p-6 border-border/60">
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-5">
          {[
            { label: "Supplier", value: shipment.supplier_name },
            { label: "Consignee", value: shipment.consignee_name },
            { label: "Incoterm", value: shipment.incoterm },
            { label: "Transport Mode", value: shipment.transport_mode },
            { label: "BOE Number", value: shipment.boe_number ? <span className="font-mono">{shipment.boe_number}</span> : null },
            { label: "BOE Version", value: (shipment.boe_version ?? 0) > 0 ? <span className="font-mono">v{shipment.boe_version}</span> : null },
            {
              label: "Last Updated",
              value: shipment.updated_at
                ? formatDistanceToNow(new Date(shipment.updated_at), { addSuffix: true })
                : null,
            },
          ]
            .filter(r => r.value)
            .map(r => (
              <div key={r.label}>
                <p className="text-xs text-muted-foreground mb-0.5">{r.label}</p>
                <p className="text-sm font-medium text-foreground">{r.value}</p>
              </div>
            ))}
        </div>
      </Card>

      {/* Step 2 — Vendor Documents */}
      <Section
        icon={<FileStack className="w-4 h-4" />}
        title="Step 2 — Vendor Documents"
        count={vendorDocs.length}
        iconBg="#5B7BA518"
        iconColor="#5B7BA5"
        emptyMessage="No vendor documents uploaded yet."
        emptyAction={
          <Link href="/validation/vendor-docs">
            <Button size="sm" style={{ background: BRAND }}>Upload Vendor Docs</Button>
          </Link>
        }
      >
        {vendorDocs.map(doc => (
          <DocumentSection key={doc.document_id} doc={doc} />
        ))}
      </Section>

      {/* Bundle PDF upload (alternative to separate file upload) */}
      <BundleUploadPanel
        shipmentId={shipmentId}
        onComplete={() => {
          // Refresh shipment data after successful bundle validation
          // (react-query will refetch on the next render cycle)
        }}
      />

      {/* Step 6 — Bill of Entry */}
      <Section
        icon={<Ship className="w-4 h-4" />}
        title="Step 6 — Bill of Entry"
        count={boeDocs.length}
        iconBg="#A0785A18"
        iconColor="#A0785A"
        emptyMessage="No Bill of Entry uploaded yet."
        emptyAction={
          <Link href="/validation/boe">
            <Button size="sm" variant="outline">Upload BOE</Button>
          </Link>
        }
      >
        {boeDocs.map(doc => (
          <DocumentSection key={doc.document_id} doc={doc} />
        ))}
      </Section>

      {/* Token usage */}
      {shipment.token_usage.length > 0 && (
        <Card className="border-border/60 overflow-hidden">
          <div className="flex items-center gap-3 px-6 py-4 border-b border-border">
            <div className="p-1.5 rounded-lg bg-muted">
              <Cpu className="w-4 h-4 text-muted-foreground" />
            </div>
            <h2 className="text-base font-semibold text-foreground">LLM Usage</h2>
          </div>
          <div className="p-5 space-y-4">
            {shipment.token_usage.map((u, i) => (
              <TokenUsageCard key={i} usage={u} />
            ))}
          </div>
        </Card>
      )}
    </div>
  )
}
