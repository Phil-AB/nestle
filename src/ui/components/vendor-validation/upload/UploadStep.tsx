"use client"

import { useRef } from "react"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { ChevronDown, ChevronUp, Settings2, Files, FileUp, X } from "lucide-react"
import { FileSlot } from "./FileSlot"
import { DOC_SLOTS } from "../lib/constants"
import type { DocFiles } from "../lib/types"

interface UploadStepProps {
  uploadMode: "separate" | "bundle"
  setUploadMode: (v: "separate" | "bundle") => void
  bundleFile: File | null
  setBundleFile: (f: File | null) => void
  bundleRequiredFilled: boolean
  onBundleValidate: () => void
  showShipmentDetails: boolean
  setShowShipmentDetails: (v: boolean) => void
  shipmentNumber: string
  setShipmentNumber: (v: string) => void
  supplierName: string
  setSupplierName: (v: string) => void
  consigneeName: string
  setConsigneeName: (v: string) => void
  incoterm: string
  setIncoterm: (v: string) => void
  transportMode: string
  setTransportMode: (v: string) => void
  files: DocFiles
  setFile: (key: keyof DocFiles, file: File | null) => void
  requiredFilled: boolean
  submitting: boolean
  onValidate: () => void
}

export function UploadStep({
  uploadMode,
  setUploadMode,
  bundleFile,
  setBundleFile,
  bundleRequiredFilled,
  onBundleValidate,
  showShipmentDetails,
  setShowShipmentDetails,
  shipmentNumber,
  setShipmentNumber,
  supplierName,
  setSupplierName,
  consigneeName,
  setConsigneeName,
  incoterm,
  setIncoterm,
  transportMode,
  setTransportMode,
  files,
  setFile,
  requiredFilled,
  submitting,
  onValidate,
}: UploadStepProps) {
  const bundleInputRef = useRef<HTMLInputElement>(null)

  return (
    <div className="space-y-4">
      {/* Mode toggle */}
      <div className="flex rounded-lg border border-border overflow-hidden">
        <button
          onClick={() => setUploadMode("separate")}
          className={`flex-1 flex items-center justify-center gap-2 py-2.5 text-sm font-medium transition-colors ${
            uploadMode === "separate"
              ? "bg-primary text-primary-foreground"
              : "bg-background text-muted-foreground hover:bg-muted/40"
          }`}
        >
          <FileUp className="w-4 h-4" />
          Separate Files
        </button>
        <button
          onClick={() => setUploadMode("bundle")}
          className={`flex-1 flex items-center justify-center gap-2 py-2.5 text-sm font-medium transition-colors border-l border-border ${
            uploadMode === "bundle"
              ? "bg-primary text-primary-foreground"
              : "bg-background text-muted-foreground hover:bg-muted/40"
          }`}
        >
          <Files className="w-4 h-4" />
          Bundle PDF
        </button>
      </div>

      {/* Shipment details (both modes) */}
      <Card className="overflow-hidden">
        <button
          className="w-full flex items-center justify-between p-4 hover:bg-muted/30 transition-colors text-left"
          onClick={() => setShowShipmentDetails(!showShipmentDetails)}
        >
          <div className="flex items-center gap-2">
            <Settings2 className="w-4 h-4 text-muted-foreground" />
            <span className="text-sm font-medium text-foreground">Shipment Details</span>
            <span className="text-xs text-muted-foreground">(optional)</span>
          </div>
          {showShipmentDetails ? (
            <ChevronUp className="w-4 h-4 text-muted-foreground" />
          ) : (
            <ChevronDown className="w-4 h-4 text-muted-foreground" />
          )}
        </button>

        {showShipmentDetails && (
          <div className="px-4 pb-4 border-t border-border pt-4 grid grid-cols-2 gap-4">
            <div className="col-span-2 md:col-span-1">
              <Label htmlFor="shipment-number" className="text-xs font-medium text-muted-foreground">Shipment Number</Label>
              <Input id="shipment-number" value={shipmentNumber} onChange={(e) => setShipmentNumber(e.target.value)} placeholder="Auto-generated if empty" className="mt-1 text-sm" />
            </div>
            <div className="col-span-2 md:col-span-1">
              <Label htmlFor="incoterm" className="text-xs font-medium text-muted-foreground">Incoterm</Label>
              <Input id="incoterm" value={incoterm} onChange={(e) => setIncoterm(e.target.value)} placeholder="e.g. CIF, FOB, DDP" className="mt-1 text-sm" />
            </div>
            <div className="col-span-2 md:col-span-1">
              <Label htmlFor="supplier-name" className="text-xs font-medium text-muted-foreground">Supplier Name</Label>
              <Input id="supplier-name" value={supplierName} onChange={(e) => setSupplierName(e.target.value)} placeholder="Extracted from invoice if empty" className="mt-1 text-sm" />
            </div>
            <div className="col-span-2 md:col-span-1">
              <Label htmlFor="transport-mode" className="text-xs font-medium text-muted-foreground">Transport Mode</Label>
              <Input id="transport-mode" value={transportMode} onChange={(e) => setTransportMode(e.target.value)} placeholder="e.g. Sea, Air, Road" className="mt-1 text-sm" />
            </div>
            <div className="col-span-2">
              <Label htmlFor="consignee-name" className="text-xs font-medium text-muted-foreground">Consignee Name</Label>
              <Input id="consignee-name" value={consigneeName} onChange={(e) => setConsigneeName(e.target.value)} placeholder="Extracted from invoice if empty" className="mt-1 text-sm" />
            </div>
          </div>
        )}
      </Card>

      {/* Separate files mode */}
      {uploadMode === "separate" && (
        <>
          <Card className="p-6 space-y-3">
            <h2 className="text-base font-semibold text-foreground mb-2">Documents</h2>
            {DOC_SLOTS.map((slot) => (
              <FileSlot
                key={slot.key}
                slot={slot}
                file={files[slot.key]}
                onSelect={(f) => setFile(slot.key, f)}
                onRemove={() => setFile(slot.key, null)}
              />
            ))}
          </Card>
          <div className="flex justify-end">
            <Button onClick={onValidate} disabled={!requiredFilled || submitting} className="bg-primary hover:bg-primary/90">
              Validate Documents
            </Button>
          </div>
        </>
      )}

      {/* Bundle PDF mode */}
      {uploadMode === "bundle" && (
        <>
          <Card className="p-6 space-y-4">
            <div>
              <h2 className="text-base font-semibold text-foreground">Bundle PDF</h2>
              <p className="text-sm text-muted-foreground mt-0.5">
                Upload a single PDF containing all documents — invoice, BOL, packing list, COO, sanitary certificate, COA, etc. The system will automatically detect and separate each document type.
              </p>
            </div>

            <input
              ref={bundleInputRef}
              type="file"
              accept=".pdf,application/pdf"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0] ?? null
                setBundleFile(f)
                e.target.value = ""
              }}
            />

            {bundleFile ? (
              <div className="flex items-center gap-3 p-3 bg-primary/5 border border-primary/20 rounded-lg">
                <Files className="w-5 h-5 text-primary flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-foreground truncate">{bundleFile.name}</p>
                  <p className="text-xs text-muted-foreground">{(bundleFile.size / 1024).toFixed(1)} KB</p>
                </div>
                <button
                  onClick={() => setBundleFile(null)}
                  className="text-muted-foreground hover:text-destructive transition-colors flex-shrink-0"
                  aria-label="Remove file"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            ) : (
              <button
                onClick={() => bundleInputRef.current?.click()}
                className="w-full flex flex-col items-center justify-center gap-3 p-10 border-2 border-dashed border-border/60 rounded-xl hover:bg-muted/20 hover:border-primary/40 transition-colors"
              >
                <Files className="w-8 h-8 text-muted-foreground" />
                <div className="text-center">
                  <p className="text-sm font-medium text-foreground">Click to select bundle PDF</p>
                  <p className="text-xs text-muted-foreground mt-0.5">All documents combined in one file</p>
                </div>
              </button>
            )}
          </Card>

          <div className="flex justify-end">
            <Button onClick={onBundleValidate} disabled={!bundleRequiredFilled || submitting} className="bg-primary hover:bg-primary/90">
              Detect &amp; Validate Bundle
            </Button>
          </div>
        </>
      )}
    </div>
  )
}
