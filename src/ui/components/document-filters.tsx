/**
 * Document Filters Component
 * Provides filtering controls for document list (type, status, search)
 */

"use client"

import { useState, useEffect } from "react"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Label } from "@/components/ui/label"
import { Search, RotateCcw } from "lucide-react"
import { type DocumentType, type ExtractionStatus } from "@/lib/api-client"

interface DocumentFilters {
  documentType?: DocumentType | "all"
  status?: ExtractionStatus | "all"
  searchTerm?: string
}

interface DocumentFiltersProps {
  filters: DocumentFilters
  onFilterChange: (filters: Partial<DocumentFilters>) => void
  onReset: () => void
}

export default function DocumentFilters({ filters, onFilterChange, onReset }: DocumentFiltersProps) {
  const [searchInput, setSearchInput] = useState(filters.searchTerm || "")

  // Document type options
  const documentTypes: { value: DocumentType | "all"; label: string }[] = [
    { value: "all", label: "All Types" },
    { value: "invoice", label: "Invoice" },
    { value: "boe", label: "Bill of Entry" },
    { value: "packing_list", label: "Packing List" },
    { value: "coo", label: "Certificate of Origin" },
    { value: "freight", label: "Freight Document" },
  ]

  // Status options
  const statusOptions: { value: ExtractionStatus | "all"; label: string }[] = [
    { value: "all", label: "All Status" },
    { value: "complete", label: "Complete" },
    { value: "incomplete", label: "Incomplete" },
    { value: "failed", label: "Failed" },
    { value: "processing", label: "Processing" },
  ]

  // Debounced search
  useEffect(() => {
    const timeoutId = setTimeout(() => {
      onFilterChange({ searchTerm: searchInput })
    }, 500) // 500ms debounce

    return () => clearTimeout(timeoutId)
  }, [searchInput, onFilterChange])

  const handleReset = () => {
    setSearchInput("")
    onReset()
  }

  return (
    <div className="space-y-4">
      {/* Search Input */}
      <div className="space-y-2">
        <Label htmlFor="search">Search Documents</Label>
        <div className="relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <Input
            id="search"
            type="text"
            placeholder="Search by document name or type..."
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            className="pl-10"
          />
        </div>
      </div>

      {/* Filters Row */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Document Type Filter */}
        <div className="space-y-2">
          <Label htmlFor="document-type">Document Type</Label>
          <Select
            value={filters.documentType || "all"}
            onValueChange={(value) => onFilterChange({ documentType: value as DocumentType | "all" })}
          >
            <SelectTrigger id="document-type">
              <SelectValue placeholder="Select type" />
            </SelectTrigger>
            <SelectContent>
              {documentTypes.map((type) => (
                <SelectItem key={type.value} value={type.value}>
                  {type.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Status Filter */}
        <div className="space-y-2">
          <Label htmlFor="status">Status</Label>
          <Select
            value={filters.status || "complete"}
            onValueChange={(value) => onFilterChange({ status: value as ExtractionStatus | "all" })}
          >
            <SelectTrigger id="status">
              <SelectValue placeholder="Select status" />
            </SelectTrigger>
            <SelectContent>
              {statusOptions.map((status) => (
                <SelectItem key={status.value} value={status.value}>
                  {status.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Reset Button */}
        <div className="space-y-2">
          <Label className="invisible">Reset</Label>
          <Button variant="outline" onClick={handleReset} className="w-full">
            <RotateCcw className="w-4 h-4 mr-2" />
            Reset Filters
          </Button>
        </div>
      </div>
    </div>
  )
}
