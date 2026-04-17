"use client"

import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { ChevronDown, ChevronUp, Settings2 } from "lucide-react"
import { FileSlot } from "./FileSlot"
import { DOC_SLOTS } from "../lib/constants"
import type { DocFiles } from "../lib/types"

interface UploadStepProps {
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
  return (
    <div className="space-y-4">
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
    </div>
  )
}
