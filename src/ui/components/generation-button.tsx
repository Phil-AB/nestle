"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Label } from "@/components/ui/label"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { FileOutput, Download, Loader, Layers } from "lucide-react"
import { apiClient, type TemplateMetadata } from "@/lib/api-client"
import { toast } from "sonner"
import { useEffect } from "react"
import MultiDocumentSelector from "@/components/multi-document-selector"

interface GenerationButtonProps {
  documentId: string
  documentType?: string
}

export default function GenerationButton({ documentId, documentType }: GenerationButtonProps) {
  const [open, setOpen] = useState(false)
  const [templates, setTemplates] = useState<TemplateMetadata[]>([])
  const [selectedTemplate, setSelectedTemplate] = useState<string>("")
  const [generating, setGenerating] = useState(false)
  const [loading, setLoading] = useState(false)
  const [mode, setMode] = useState<"single" | "multi">("single")
  const [selectedDocumentIds, setSelectedDocumentIds] = useState<string[]>([])
  const [mergeStrategy, setMergeStrategy] = useState<"prioritized" | "best_available" | "all_required">("prioritized")

  useEffect(() => {
    if (open) {
      loadTemplates()
    }
  }, [open])

  const loadTemplates = async () => {
    setLoading(true)
    try {
      const response = await apiClient.listTemplates()
      setTemplates(response.templates)
      
      // Auto-select first template
      if (response.templates.length > 0 && !selectedTemplate) {
        setSelectedTemplate(response.templates[0].template_id)
      }
    } catch (error) {
      toast.error("Failed to load templates")
      console.error(error)
    } finally {
      setLoading(false)
    }
  }

  const handleGenerate = async () => {
    if (!selectedTemplate) {
      toast.error("Please select a template")
      return
    }

    // Validate multi-source mode
    if (mode === "multi" && selectedDocumentIds.length === 0) {
      toast.error("Please select at least one source document")
      return
    }

    setGenerating(true)
    try {
      let result

      if (mode === "multi") {
        // Multi-source generation
        result = await apiClient.generateMultiSourceDocument(
          selectedTemplate,
          selectedDocumentIds,
          mergeStrategy,
          selectedTemplate // Use same ID for mapping
        )
      } else {
        // Single-source generation (existing behavior)
        result = await apiClient.generateDocument(
          selectedTemplate,
          {
            provider: "postgres",
            query: { document_id: documentId },
          },
          selectedTemplate // Use same ID for mapping
        )
      }

      if (result.success && result.job_id) {
        const docCount = mode === "multi" ? selectedDocumentIds.length : 1
        toast.success(
          `Document generated from ${docCount} source${docCount > 1 ? "s" : ""} in ${result.generation_time_ms?.toFixed(0)}ms`,
          {
            description: "Downloading...",
          }
        )

        // Download the file
        const blob = await apiClient.downloadGeneratedDocument(result.job_id)
        const url = window.URL.createObjectURL(blob)
        const a = document.createElement("a")
        a.href = url

        const template = templates.find(t => t.template_id === selectedTemplate)
        const filename = mode === "multi"
          ? `${template?.template_name || "document"}_merged.${template?.template_format || "docx"}`
          : `${template?.template_name || "document"}_${documentId}.${template?.template_format || "docx"}`
        a.download = filename
        a.click()
        window.URL.revokeObjectURL(url)

        toast.success("Document downloaded successfully!")
        setOpen(false)
      } else {
        toast.error(`Generation failed: ${result.message}`)
      }
    } catch (error) {
      toast.error("Failed to generate document")
      console.error(error)
    } finally {
      setGenerating(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm">
          <FileOutput className="w-4 h-4 mr-2" />
          Generate Document
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Generate Document</DialogTitle>
          <DialogDescription>
            Generate a document from single or multiple source documents
          </DialogDescription>
        </DialogHeader>

        <Tabs value={mode} onValueChange={(v) => setMode(v as "single" | "multi")} className="w-full">
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="single">
              <FileOutput className="w-4 h-4 mr-2" />
              Single Source
            </TabsTrigger>
            <TabsTrigger value="multi">
              <Layers className="w-4 h-4 mr-2" />
              Multi-Source
            </TabsTrigger>
          </TabsList>

          <TabsContent value="single" className="space-y-4 mt-4">
            <p className="text-sm text-muted-foreground">
              Generate from the current document only
            </p>

            {/* Template Selection */}
            <div className="space-y-2">
              <Label htmlFor="template">Template</Label>
              {loading ? (
                <div className="flex items-center justify-center py-8">
                  <Loader className="w-6 h-6 animate-spin text-muted-foreground" />
                </div>
              ) : (
                <Select value={selectedTemplate} onValueChange={setSelectedTemplate}>
                  <SelectTrigger id="template">
                    <SelectValue placeholder="Select a template" />
                  </SelectTrigger>
                  <SelectContent>
                    {templates.map((template) => (
                      <SelectItem key={template.template_id} value={template.template_id}>
                        <div className="flex items-center justify-between w-full">
                          <span>{template.template_name}</span>
                          <span className="text-xs text-muted-foreground ml-2">
                            ({template.template_format.toUpperCase()})
                          </span>
                        </div>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            </div>

            {selectedTemplate && (
              <div className="rounded-lg bg-muted p-3 text-sm">
                {(() => {
                  const template = templates.find((t) => t.template_id === selectedTemplate)
                  if (!template) return null
                  return (
                    <div className="space-y-1">
                      <p className="font-medium">{template.template_name}</p>
                      <p className="text-muted-foreground text-xs">{template.description}</p>
                      <div className="flex gap-2 mt-2">
                        <span className="text-xs bg-background px-2 py-1 rounded">
                          {template.required_fields.length} required fields
                        </span>
                        {template.supports_tables && (
                          <span className="text-xs bg-background px-2 py-1 rounded">
                            Tables supported
                          </span>
                        )}
                      </div>
                    </div>
                  )
                })()}
              </div>
            )}
          </TabsContent>

          <TabsContent value="multi" className="space-y-4 mt-4">
            <p className="text-sm text-muted-foreground">
              Combine data from multiple documents using a merge strategy
            </p>

            {/* Template Selection */}
            <div className="space-y-2">
              <Label htmlFor="template-multi">Template</Label>
              {loading ? (
                <div className="flex items-center justify-center py-8">
                  <Loader className="w-6 h-6 animate-spin text-muted-foreground" />
                </div>
              ) : (
                <Select value={selectedTemplate} onValueChange={setSelectedTemplate}>
                  <SelectTrigger id="template-multi">
                    <SelectValue placeholder="Select a template" />
                  </SelectTrigger>
                  <SelectContent>
                    {templates.map((template) => (
                      <SelectItem key={template.template_id} value={template.template_id}>
                        <div className="flex items-center justify-between w-full">
                          <span>{template.template_name}</span>
                          <span className="text-xs text-muted-foreground ml-2">
                            ({template.template_format.toUpperCase()})
                          </span>
                        </div>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            </div>

            {/* Merge Strategy Selection */}
            <div className="space-y-2">
              <Label htmlFor="merge-strategy">Merge Strategy</Label>
              <Select value={mergeStrategy} onValueChange={(v) => setMergeStrategy(v as any)}>
                <SelectTrigger id="merge-strategy">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="prioritized">
                    <div className="flex flex-col items-start">
                      <span className="font-medium">Prioritized</span>
                      <span className="text-xs text-muted-foreground">First document wins for conflicts</span>
                    </div>
                  </SelectItem>
                  <SelectItem value="best_available">
                    <div className="flex flex-col items-start">
                      <span className="font-medium">Best Available</span>
                      <span className="text-xs text-muted-foreground">Most complete value wins</span>
                    </div>
                  </SelectItem>
                  <SelectItem value="all_required">
                    <div className="flex flex-col items-start">
                      <span className="font-medium">All Required</span>
                      <span className="text-xs text-muted-foreground">Only common fields included</span>
                    </div>
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Document Selector */}
            <MultiDocumentSelector
              selectedDocumentIds={selectedDocumentIds}
              onSelectionChange={setSelectedDocumentIds}
              excludeDocumentId={documentId}
              minDocuments={1}
              maxDocuments={10}
            />
          </TabsContent>
        </Tabs>

        <div className="flex gap-2 pt-4 border-t">
          <Button variant="outline" onClick={() => setOpen(false)} className="flex-1">
            Cancel
          </Button>
          <Button
            onClick={handleGenerate}
            disabled={!selectedTemplate || generating || (mode === "multi" && selectedDocumentIds.length === 0)}
            className="flex-1"
          >
            {generating ? (
              <>
                <Loader className="w-4 h-4 mr-2 animate-spin" />
                Generating...
              </>
            ) : (
              <>
                <Download className="w-4 h-4 mr-2" />
                Generate & Download
              </>
            )}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
