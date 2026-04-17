"use client"

import { FileText } from "lucide-react"
import { DOC_LABEL } from "../lib/constants"

interface DocumentViewerProps {
  files: Record<string, File | null>
  activeDocKey: string | null
  setActiveDocKey: (key: string | null) => void
  getDocBlobUrl: (key: string) => string | null
}

export function DocumentViewer({
  files,
  activeDocKey,
  setActiveDocKey,
  getDocBlobUrl,
}: DocumentViewerProps) {
  const uploadedDocs = Object.entries(files).filter(([, f]) => f !== null) as [string, File][]
  const currentKey = activeDocKey ?? uploadedDocs[0]?.[0] ?? null
  const currentFile = currentKey ? files[currentKey] : null
  const blobUrl = currentKey ? getDocBlobUrl(currentKey) : null
  const isPdf = currentFile?.type === "application/pdf" || currentFile?.name?.toLowerCase().endsWith(".pdf")

  return (
    <div className="flex gap-4 h-[780px]">
      {/* Sidebar — document list */}
      <div className="w-52 flex-shrink-0 flex flex-col gap-1">
        <p className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground px-1 mb-1">
          Uploaded Files
        </p>
        {uploadedDocs.map(([key, file]) => (
          <button
            key={key}
            onClick={() => setActiveDocKey(key)}
            className={`text-left px-3 py-2.5 rounded-lg border transition-colors ${
              currentKey === key
                ? "border-primary bg-primary/5 text-primary"
                : "border-border hover:bg-muted/50 text-foreground"
            }`}
          >
            <div className="flex items-center gap-2">
              <FileText className={`w-3.5 h-3.5 flex-shrink-0 ${currentKey === key ? "text-primary" : "text-muted-foreground"}`} />
              <div className="min-w-0">
                <p className="text-[12px] font-semibold truncate">
                  {DOC_LABEL[key] ?? key.replace(/_/g, " ")}
                </p>
                <p className="text-[10px] text-muted-foreground truncate mt-0.5" title={file.name}>
                  {file.name}
                </p>
              </div>
            </div>
          </button>
        ))}
        {uploadedDocs.length === 0 && (
          <p className="text-xs text-muted-foreground px-1">No files uploaded.</p>
        )}
      </div>

      {/* Viewer pane */}
      <div className="flex-1 min-w-0 rounded-lg border border-border overflow-hidden bg-muted/20">
        {blobUrl && currentFile ? (
          isPdf ? (
            <iframe
              key={currentKey}
              src={blobUrl}
              title={DOC_LABEL[currentKey!] ?? currentKey!}
              className="w-full h-full border-0"
            />
          ) : (
            <div className="w-full h-full flex items-center justify-center overflow-auto p-4">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                key={currentKey}
                src={blobUrl}
                alt={DOC_LABEL[currentKey!] ?? currentKey!}
                className="max-w-full max-h-full object-contain rounded"
              />
            </div>
          )
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <p className="text-sm text-muted-foreground">Select a document to preview</p>
          </div>
        )}
      </div>
    </div>
  )
}
