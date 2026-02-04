"use client"

import { useQuery } from '@tanstack/react-query'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Loader2 } from 'lucide-react'
import { apiClient } from '@/lib/api-client'

interface DocumentType {
  id: string
  display_name: string
  description: string
  category: string
  icon: string
}

interface DocumentTypeSelectProps {
  value?: string
  onChange: (value: string) => void
  placeholder?: string
  disabled?: boolean
}

export function DocumentTypeSelect({
  value,
  onChange,
  placeholder = "Select document type",
  disabled = false
}: DocumentTypeSelectProps) {
  const { data: typesData, isLoading, error } = useQuery({
    queryKey: ['document-types'],
    queryFn: async () => {
      const response = await apiClient.getDocumentTypes()
      console.log('Document types response:', response)
      return response
    },
    staleTime: 5 * 60 * 1000, // 5 minutes
  })

  if (isLoading) {
    return (
      <Select disabled>
        <SelectTrigger>
          <div className="flex items-center gap-2">
            <Loader2 className="h-4 w-4 animate-spin" />
            <span>Loading document types...</span>
          </div>
        </SelectTrigger>
      </Select>
    )
  }

  if (error) {
    return (
      <Select disabled>
        <SelectTrigger>
          <span className="text-destructive">Failed to load document types</span>
        </SelectTrigger>
      </Select>
    )
  }

  const types = typesData?.types || []

  return (
    <Select value={value || "__none__"} onValueChange={(val) => onChange(val === "__none__" ? "" : val)} disabled={disabled}>
      <SelectTrigger>
        <SelectValue placeholder={placeholder} />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="__none__">
          <em>None - Auto-detect later</em>
        </SelectItem>
        {types.map((type: DocumentType) => (
          <SelectItem key={type.id} value={type.id}>
            <div className="flex flex-col">
              <span className="font-medium">{type.display_name}</span>
              {type.description && (
                <span className="text-sm text-muted-foreground">
                  {type.description}
                </span>
              )}
            </div>
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}

export default DocumentTypeSelect