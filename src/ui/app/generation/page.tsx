"use client"

// API URL configuration - reads from environment or uses default
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL?.replace("/v1", "/v2") || "http://54.87.52.48:8000/api/v2"

import { useEffect, useState } from "react"
import { apiClient, type FormMetadata, type PopulationResponse, type DocumentResponse } from "@/lib/api-client"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Badge } from "@/components/ui/badge"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Label } from "@/components/ui/label"
import { Loader, FileText, Download, CheckCircle, XCircle, Clock, RefreshCw, Layers, ArrowLeft } from "lucide-react"
import { toast } from "sonner"
import DocumentSelector from "@/components/document-selector"
import SelectedDocumentBanner from "@/components/selected-document-banner"
import MultiDocumentSelector from "@/components/multi-document-selector"

type GenerationStep = 'select-mode' | 'select-document' | 'select-form'
type GenerationMode = 'single' | 'multi'

export default function GenerationPage() {
  // Mode and step management
  const [mode, setMode] = useState<GenerationMode>('single')
  const [currentStep, setCurrentStep] = useState<GenerationStep>('select-mode')
  const [selectedDocument, setSelectedDocument] = useState<DocumentResponse | null>(null)
  const [selectedDocumentIds, setSelectedDocumentIds] = useState<string[]>([])
  const [mergeStrategy, setMergeStrategy] = useState<"prioritized" | "best_available" | "combine">("best_available")

  // Existing state
  const [forms, setForms] = useState<FormMetadata[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedForm, setSelectedForm] = useState<FormMetadata | null>(null)
  const [isPopulating, setIsPopulating] = useState(false)

  useEffect(() => {
    loadForms()
  }, [])

  const loadForms = async () => {
    try {
      const formsList = await apiClient.listForms()
      setForms(formsList)
    } catch (error) {
      toast.error("Failed to load forms")
      console.error(error)
    } finally {
      setLoading(false)
    }
  }

  // Handle mode selection
  const handleModeSelect = (selectedMode: GenerationMode) => {
    setMode(selectedMode)
    if (selectedMode === 'single') {
      setCurrentStep('select-document')
    } else {
      setCurrentStep('select-form') // Multi-mode goes straight to form selection
    }
  }

  // Handle document selection (Step 1 → Step 2) - Single mode
  const handleDocumentSelect = (document: DocumentResponse) => {
    setSelectedDocument(document)
    setCurrentStep('select-form')
    toast.success(`Selected: ${document.document_number || document.document_id.slice(0, 8)}`)
  }

  // Handle changing document (Step 2 → Step 1)
  const handleChangeDocument = () => {
    if (mode === 'single') {
      setCurrentStep('select-document')
    } else {
      setCurrentStep('select-mode')
    }
  }

  // Handle back to mode selection
  const handleBackToMode = () => {
    setCurrentStep('select-mode')
    setSelectedDocument(null)
    setSelectedDocumentIds([])
  }

  // Generate form with selected document's data
  const handlePopulateForm = async (form: FormMetadata) => {
    // Validation based on mode
    if (mode === 'single' && !selectedDocument) {
      toast.error('No document selected. Please select a document first.')
      setCurrentStep('select-document')
      return
    }

    if (mode === 'multi' && selectedDocumentIds.length === 0) {
      toast.error('No documents selected. Please select at least one document.')
      return
    }

    setIsPopulating(true)
    setSelectedForm(form)

    try {
      const toastId = toast.loading("Generating form...")

      // Get document IDs
      const documentIds = mode === 'single'
        ? [selectedDocument!.document_id]
        : selectedDocumentIds

      // Call generation API with selected form
      const result = await apiClient.populateForm(
        form.form_id,
        documentIds,
        {
          mergeStrategy: mergeStrategy,
          flattenForm: false  // Keep editable
        }
      )

      if (result.success && result.output_path) {
        // Extract filename from output path
        const filename = result.output_path.split('/').pop() || `document_generated_${Date.now()}.pdf`

        // Download the generated PDF using the download endpoint
        const blob = await fetch(`${API_BASE_URL}/population/download/${filename}`)
          .then(r => r.blob())

        // Trigger download
        const url = window.URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = filename
        a.click()
        window.URL.revokeObjectURL(url)

        toast.success(
          `Form generated with ${documentIds.length} document(s)`,
          { id: toastId, duration: 3000 }
        )
      } else {
        toast.error(`Generation failed: ${result.error}`, { id: toastId })
      }
    } catch (error: any) {
      toast.error(`Error: ${error.message}`)
      console.error(error)
    } finally {
      setIsPopulating(false)
    }
  }

  if (loading) {
    return (
      <div className="flex justify-center items-center min-h-screen">
        <Loader className="w-8 h-8 animate-spin text-primary" />
      </div>
    )
  }

  return (
    <div className="container mx-auto py-8 px-4">
      <div className="mb-8">
        <h1 className="text-4xl font-bold mb-2">Document Generation</h1>
        <p className="text-muted-foreground">
          Generate documents from template data using single or multiple source documents
        </p>
      </div>

      {/* Step 0: Select Mode */}
      {currentStep === 'select-mode' && (
        <div className="max-w-4xl mx-auto space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Select Generation Mode</CardTitle>
              <CardDescription>
                Choose whether to generate from a single document or combine multiple documents
              </CardDescription>
            </CardHeader>
          </Card>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Single Source Mode Card */}
            <Card
              className="cursor-pointer hover:shadow-lg transition-all hover:border-primary"
              onClick={() => handleModeSelect('single')}
            >
              <CardHeader>
                <div className="flex items-center gap-3">
                  <div className="p-3 rounded-lg bg-blue-100 text-blue-600">
                    <FileText className="w-8 h-8" />
                  </div>
                  <div>
                    <CardTitle>Single Document</CardTitle>
                    <CardDescription className="mt-1">
                      Generate from one document
                    </CardDescription>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground mb-4">
                  Use data from a single extracted document as the source for generation.
                  Best for standard document workflows.
                </p>
                <ul className="space-y-2 text-sm">
                  <li className="flex items-center gap-2">
                    <CheckCircle className="w-4 h-4 text-green-600" />
                    Simple and straightforward
                  </li>
                  <li className="flex items-center gap-2">
                    <CheckCircle className="w-4 h-4 text-green-600" />
                    Fast processing
                  </li>
                  <li className="flex items-center gap-2">
                    <CheckCircle className="w-4 h-4 text-green-600" />
                    No data merging required
                  </li>
                </ul>
              </CardContent>
            </Card>

            {/* Multiple Documents Mode Card */}
            <Card
              className="cursor-pointer hover:shadow-lg transition-all hover:border-primary"
              onClick={() => handleModeSelect('multi')}
            >
              <CardHeader>
                <div className="flex items-center gap-3">
                  <div className="p-3 rounded-lg bg-purple-100 text-purple-600">
                    <Layers className="w-8 h-8" />
                  </div>
                  <div>
                    <CardTitle>Multiple Documents</CardTitle>
                    <CardDescription className="mt-1">
                      Combine data from multiple documents
                    </CardDescription>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground mb-4">
                  Merge data from multiple documents with intelligent conflict resolution.
                  Choose from multiple merge strategies to handle overlapping fields.
                </p>
                <ul className="space-y-2 text-sm">
                  <li className="flex items-center gap-2">
                    <CheckCircle className="w-4 h-4 text-green-600" />
                    Combine complementary data
                  </li>
                  <li className="flex items-center gap-2">
                    <CheckCircle className="w-4 h-4 text-green-600" />
                    Smart conflict resolution
                  </li>
                  <li className="flex items-center gap-2">
                    <CheckCircle className="w-4 h-4 text-green-600" />
                    Source tracking for audit
                  </li>
                </ul>
              </CardContent>
            </Card>
          </div>
        </div>
      )}

      {/* Step 1: Select Source Document (Single Mode Only) */}
      {currentStep === 'select-document' && mode === 'single' && (
        <div>
          <Button
            variant="ghost"
            className="mb-4"
            onClick={handleBackToMode}
          >
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Mode Selection
          </Button>
          <DocumentSelector onDocumentSelect={handleDocumentSelect} />
        </div>
      )}

      {/* Step 2: Select Form & Generate */}
      {currentStep === 'select-form' && (mode === 'single' ? selectedDocument : true) && (
        <div className="space-y-6">
          {/* Back Button */}
          <Button
            variant="ghost"
            onClick={handleChangeDocument}
          >
            <ArrowLeft className="w-4 h-4 mr-2" />
            {mode === 'single' ? 'Change Document' : 'Back to Mode Selection'}
          </Button>

          {/* Selected Document Banner (Single Mode) */}
          {mode === 'single' && selectedDocument && (
            <SelectedDocumentBanner
              document={selectedDocument}
              onDeselect={handleChangeDocument}
            />
          )}

          {/* Multiple Documents Selection */}
          {mode === 'multi' && (
            <Card>
              <CardHeader>
                <CardTitle>Multi-Document Configuration</CardTitle>
                <CardDescription>
                  Select multiple documents and choose a merge strategy
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                {/* Merge Strategy Selector */}
                <div className="space-y-2">
                  <Label htmlFor="merge-strategy">Merge Strategy</Label>
                  <Select value={mergeStrategy} onValueChange={(v) => setMergeStrategy(v as any)}>
                    <SelectTrigger id="merge-strategy">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="prioritized">
                        <div className="flex flex-col items-start py-1">
                          <span className="font-medium">Prioritized</span>
                          <span className="text-xs text-muted-foreground">
                            First document in list wins for field conflicts
                          </span>
                        </div>
                      </SelectItem>
                      <SelectItem value="best_available">
                        <div className="flex flex-col items-start py-1">
                          <span className="font-medium">Best Available</span>
                          <span className="text-xs text-muted-foreground">
                            Most complete/reliable value wins
                          </span>
                        </div>
                      </SelectItem>
                      <SelectItem value="combine">
                        <div className="flex flex-col items-start py-1">
                          <span className="font-medium">Combine</span>
                          <span className="text-xs text-muted-foreground">
                            Merge all non-duplicate fields and items
                          </span>
                        </div>
                      </SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                {/* Document Selector */}
                <MultiDocumentSelector
                  selectedDocumentIds={selectedDocumentIds}
                  onSelectionChange={setSelectedDocumentIds}
                  minDocuments={1}
                  maxDocuments={10}
                />
              </CardContent>
            </Card>
          )}

          {/* Forms Section */}
          <Card>
            <CardHeader>
              <CardTitle>Select Form to Generate</CardTitle>
              <CardDescription>
                Choose which form to generate with your document{mode === 'multi' ? 's' : ''}
              </CardDescription>
            </CardHeader>
            <CardContent>
              {forms.length === 0 ? (
                <div className="text-center py-12">
                  <FileText className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
                  <p className="text-muted-foreground">No forms available</p>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {forms.map((form) => (
                    <Card key={form.form_id} className="hover:shadow-lg transition-shadow">
                      <CardHeader>
                        <div className="flex items-start justify-between">
                          <div>
                            <CardTitle className="text-lg">{form.form_name}</CardTitle>
                            <CardDescription className="mt-1">
                              {form.description}
                            </CardDescription>
                          </div>
                          <Badge variant="outline">PDF</Badge>
                        </div>
                      </CardHeader>
                      <CardContent>
                        <div className="space-y-3">
                          <div className="text-sm">
                            <p className="text-muted-foreground">📋 {form.field_count} fields</p>
                            {form.required_document_types && form.required_document_types.length > 0 && (
                              <p className="text-muted-foreground mt-1">
                                📄 {form.required_document_types.join(', ')}
                              </p>
                            )}
                          </div>

                          <div className="flex gap-2 pt-2">
                            <Button
                              onClick={() => setSelectedForm(form)}
                              variant="outline"
                              size="sm"
                              className="flex-1"
                            >
                              <FileText className="w-4 h-4 mr-2" />
                              Details
                            </Button>
                            <Button
                              onClick={() => handlePopulateForm(form)}
                              size="sm"
                              className="flex-1"
                              disabled={isPopulating}
                            >
                              {isPopulating ? (
                                <>
                                  <Loader className="w-4 h-4 mr-2 animate-spin" />
                                  Generating...
                                </>
                              ) : (
                                <>
                                  <Download className="w-4 h-4 mr-2" />
                                  Generate
                                </>
                              )}
                            </Button>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {/* Form Details Modal */}
      {selectedForm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
          <Card className="max-w-2xl w-full max-h-[80vh] overflow-auto">
            <CardHeader>
              <div className="flex justify-between items-start">
                <div>
                  <CardTitle>{selectedForm.form_name}</CardTitle>
                  <CardDescription className="mt-2">
                    {selectedForm.description}
                  </CardDescription>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setSelectedForm(null)}
                >
                  ✕
                </Button>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <h4 className="font-semibold mb-2">Form Info</h4>
                <div className="grid grid-cols-2 gap-2 text-sm">
                  <div>
                    <span className="text-muted-foreground">ID:</span> {selectedForm.form_id}
                  </div>
                  <div>
                    <span className="text-muted-foreground">Fields:</span> {selectedForm.field_count}
                  </div>
                  <div>
                    <span className="text-muted-foreground">Format:</span> PDF
                  </div>
                  <div>
                    <span className="text-muted-foreground">Editable:</span> Yes
                  </div>
                </div>
              </div>

              {selectedForm.required_document_types && selectedForm.required_document_types.length > 0 && (
                <div>
                  <h4 className="font-semibold mb-2">Required Documents</h4>
                  <div className="flex flex-wrap gap-2">
                    {selectedForm.required_document_types.map((docType) => (
                      <Badge key={docType} variant="secondary">{docType}</Badge>
                    ))}
                  </div>
                </div>
              )}

              <div className="pt-4 flex gap-2">
                <Button
                  onClick={() => handlePopulateForm(selectedForm)}
                  className="flex-1"
                  disabled={isPopulating}
                >
                  {isPopulating ? (
                    <>
                      <Loader className="w-4 h-4 mr-2 animate-spin" />
                      Generating...
                    </>
                  ) : (
                    <>
                      <Download className="w-4 h-4 mr-2" />
                      Generate Form
                    </>
                  )}
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  )
}
