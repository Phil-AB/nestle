"use client"

import type React from "react"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Label } from "@/components/ui/label"
import { FileUp, CheckCircle, Loader, FileText, Layers } from "lucide-react"
import { api } from "@/lib/api"
import MultiFileUpload from "@/components/multi-file-upload"
import { apiClient } from "@/lib/api-client"
import DocumentTypeSelect from "@/components/document-type-select"

export default function UploadForm() {
  const router = useRouter()
  const [files, setFiles] = useState<File[]>([])
  const [uploading, setUploading] = useState(false)
  const [documentType, setDocumentType] = useState("")
  const [documentName, setDocumentName] = useState("")
  const [uploadedFiles, setUploadedFiles] = useState<any[]>([])
  const [currentStep, setCurrentStep] = useState<"upload" | "validate" | "complete">("upload")
  const [uploadMode, setUploadMode] = useState<"single" | "multi">("single")
  const [multiFiles, setMultiFiles] = useState<File[]>([])

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    const droppedFiles = Array.from(e.dataTransfer.files)
    setFiles([...files, ...droppedFiles])
  }

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const newFiles = Array.from(e.target.files)
      setFiles([...files, ...newFiles])
      // Reset input to allow selecting same file again
      e.target.value = ''
    }
  }

  const removeFile = (index: number) => {
    setFiles(files.filter((_, i) => i !== index))
  }

  const handleUpload = async () => {
    if (uploadMode === "single" && files.length === 0) return
    if (uploadMode === "multi" && multiFiles.length === 0) return

    setUploading(true)
    setCurrentStep("validate")

    try {
      const results = []
      // Convert "__none__" back to undefined for API
      const docType = documentType === "__none__" ? undefined : (documentType.trim() || "document")

      if (uploadMode === "single") {
        // Single file uploads (existing logic)
        for (const file of files) {
          const response = await api.uploadDocument(file, docType, {
            documentName: documentName || file.name
          })

          results.push({
            id: response.document_id,
            name: documentName || file.name,
            type: docType,
            size: (file.size / 1024).toFixed(2),
            status: "validated",
            uploadedAt: new Date().toLocaleString(),
          })
        }
        setFiles([])
      } else {
        // Multi-page upload
        const response = await apiClient.uploadMultiPageDocument(multiFiles, docType, {
          documentName: documentName || "Multi-page document"
        })

        results.push({
          id: response.document_id,
          name: `${multiFiles.length} pages document`,
          type: docType,
          size: multiFiles.reduce((total, file) => total + file.size, 0) / 1024,
          status: "processing",
          uploadedAt: new Date().toLocaleString(),
        })
        setMultiFiles([])
      }

      setUploadedFiles([...uploadedFiles, ...results])

      // Redirect to document view page for the first uploaded document
      if (results.length > 0) {
        router.push(`/documents/${results[0].id}`)
      } else {
        setCurrentStep("complete")
      }
    } catch (error) {
      console.error("Upload failed", error)
      // Reset to upload step on error so user can try again
      setCurrentStep("upload")
      // Toast is handled in api.ts
    } finally {
      setUploading(false)
    }
  }

  const handleNewUpload = () => {
    setCurrentStep("upload")
    setUploadedFiles([])
    setFiles([])
    setUploading(false)
    // Keep documentType and documentName so user doesn't have to re-enter them
  }

  const handleCancel = () => {
    setFiles([])
    setMultiFiles([])
    setDocumentType("")
    setDocumentName("")
    setUploading(false)
    setCurrentStep("upload")
  }

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="mb-8">
        <h1 className="text-4xl font-bold text-foreground mb-2">Upload Document</h1>
        <p className="text-muted-foreground">
          Upload and validate your business documents for processing and shipment tracking.
        </p>
      </div>

      {currentStep === "upload" && (
        <div className="space-y-6">
          {/* Document Metadata */}
          <Card className="p-6">
            <div className="space-y-4">
              <div>
                <Label htmlFor="document-name" className="text-sm font-semibold">
                  Document Name
                </Label>
                <Input
                  id="document-name"
                  type="text"
                  value={documentName}
                  onChange={(e) => setDocumentName(e.target.value)}
                  placeholder="e.g., Invoice #123, Purchase Order ABC"
                  className="w-full mt-1"
                />
                <p className="text-xs text-muted-foreground mt-1">
                  Optional: A descriptive name for your document
                </p>
              </div>

              <div>
                <Label htmlFor="document-type" className="text-sm font-semibold">
                  Document Type
                </Label>
                <div className="mt-1">
                  <DocumentTypeSelect
                    value={documentType}
                    onChange={setDocumentType}
                    placeholder="Select document type (optional)"
                  />
                </div>
                <p className="text-xs text-muted-foreground mt-1">
                  Optional: Select from available types or leave empty for auto-detection
                </p>
              </div>
            </div>
          </Card>

          {/* Upload Mode Tabs */}
          <Tabs value={uploadMode} onValueChange={(value) => setUploadMode(value as "single" | "multi")} className="w-full">
            <TabsList className="grid w-full grid-cols-2">
              <TabsTrigger value="single" className="flex items-center gap-2">
                <FileText className="w-4 h-4" />
                Single Page
              </TabsTrigger>
              <TabsTrigger value="multi" className="flex items-center gap-2">
                <Layers className="w-4 h-4" />
                Multi-Page
              </TabsTrigger>
            </TabsList>

            {/* Single Page Tab */}
            <TabsContent value="single" className="space-y-4">
              <Card
                onDrop={handleDrop}
                onDragOver={(e) => e.preventDefault()}
                className="p-12 border-2 border-dashed border-border hover:border-primary transition-colors cursor-pointer"
              >
                <div className="flex flex-col items-center justify-center text-center">
                  <div className="p-4 bg-primary/10 rounded-lg mb-4">
                    <FileUp className="w-8 h-8 text-primary" />
                  </div>
                  <h3 className="text-lg font-semibold text-foreground mb-1">Drop file here or click to browse</h3>
                  <p className="text-sm text-muted-foreground mb-4">
                    Upload a single document
                  </p>
                  <Input type="file" multiple onChange={handleFileSelect} className="hidden" id="file-input" />
                  <Button
                    onClick={() => document.getElementById("file-input")?.click()}
                    className="bg-primary hover:bg-primary/90"
                  >
                    Select File
                  </Button>
                </div>
              </Card>

              {/* Single Files List */}
              {files.length > 0 && (
                <Card className="p-6">
                  <h3 className="text-lg font-semibold text-foreground mb-4">Selected Files ({files.length})</h3>
                  <div className="space-y-2">
                    {files.map((file, i) => (
                      <div key={i} className="flex items-center justify-between p-3 bg-muted rounded-lg">
                        <div className="flex items-center gap-3 flex-1">
                          <FileUp className="w-5 h-5 text-primary" />
                          <div className="flex-1 min-w-0">
                            <p className="font-medium text-foreground truncate">{file.name}</p>
                            <p className="text-sm text-muted-foreground">{(file.size / 1024).toFixed(2)} KB</p>
                          </div>
                        </div>
                        <button onClick={() => removeFile(i)} className="text-destructive hover:text-destructive/80 ml-4">
                          Remove
                        </button>
                      </div>
                    ))}
                  </div>
                </Card>
              )}
            </TabsContent>

            {/* Multi-Page Tab */}
            <TabsContent value="multi" className="space-y-4">
              <Card className="p-6">
                <h3 className="text-lg font-semibold text-foreground mb-4">Upload Multiple Pages</h3>
                <p className="text-sm text-muted-foreground mb-6">
                  Upload multiple files that will be combined into a single document. You can reorder pages before uploading.
                </p>
                <MultiFileUpload
                  onFilesChange={setMultiFiles}
                  maxFiles={20}
                  acceptedTypes={{
                    'application/pdf': ['.pdf'],
                    'application/msword': ['.doc'],
                    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
                    'image/jpeg': ['.jpg', '.jpeg'],
                    'image/png': ['.png']
                  }}
                />
              </Card>
            </TabsContent>
          </Tabs>

          {/* Action Buttons */}
          <div className="flex gap-4 justify-end">
            <Button variant="outline" onClick={handleCancel} disabled={uploading}>
              Cancel
            </Button>
            <Button
              onClick={handleUpload}
              disabled={((uploadMode === "single" && !files.length) || (uploadMode === "multi" && !multiFiles.length)) || uploading}
              className="bg-primary hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed"
              type="button"
            >
              {uploading ? (
                <>
                  <Loader className="w-4 h-4 mr-2 animate-spin" />
                  Uploading...
                </>
              ) : uploadMode === "single" ? (
                "Upload Document"
              ) : (
                uploadMode === "multi" && multiFiles.length > 0
                  ? `Upload ${multiFiles.length} Page${multiFiles.length !== 1 ? "s" : ""} as Document`
                  : "Upload Documents"
              )}
            </Button>
          </div>
        </div>
      )}

      {currentStep === "validate" && (
        <Card className="p-12 text-center">
          <div className="flex justify-center mb-6">
            <div className="p-4 bg-primary/10 rounded-lg">
              <Loader className="w-8 h-8 text-primary animate-spin" />
            </div>
          </div>
          <h2 className="text-2xl font-bold text-foreground mb-2">Validating Documents</h2>
          <p className="text-muted-foreground">
            Your documents are being processed and validated. This may take a few moments...
          </p>
        </Card>
      )}

      {currentStep === "complete" && (
        <div className="space-y-6">
          <Card className="p-8 border-l-4 border-green-500">
            <div className="flex items-start gap-4">
              <div className="p-3 bg-green-100 rounded-lg">
                <CheckCircle className="w-6 h-6 text-green-600" />
              </div>
              <div>
                <h2 className="text-xl font-bold text-foreground mb-1">Upload Successful</h2>
                <p className="text-muted-foreground">
                  {uploadedFiles.length} document(s) have been successfully uploaded and validated.
                </p>
              </div>
            </div>
          </Card>

          {/* Uploaded Files Summary */}
          <Card className="p-6">
            <h3 className="text-lg font-semibold text-foreground mb-4">Upload Summary</h3>
            <div className="space-y-3">
              {uploadedFiles.map((file) => (
                <div key={file.id} className="flex items-center justify-between p-3 bg-muted rounded-lg">
                  <div className="flex items-center gap-3 flex-1">
                    <CheckCircle className="w-5 h-5 text-green-600" />
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-foreground truncate">{file.name}</p>
                      <p className="text-sm text-muted-foreground">
                        {file.type.toUpperCase()} • {file.size} KB
                      </p>
                    </div>
                  </div>
                  <span className="text-sm font-medium text-green-600">Validated</span>
                </div>
              ))}
            </div>
          </Card>

          {/* Next Steps */}
          <div className="flex gap-4">
            <Button onClick={handleNewUpload} variant="outline" className="flex-1 bg-transparent">
              Upload More
            </Button>
            <Button 
              onClick={() => router.push('/documents')} 
              className="flex-1 bg-primary hover:bg-primary/90"
            >
              View All Documents
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
