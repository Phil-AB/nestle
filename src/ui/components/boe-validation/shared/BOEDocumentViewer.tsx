"use client"

interface BOEDocumentViewerProps {
  boeFile: File | null
  getBOEBlobUrl: () => string | null
}

export function BOEDocumentViewer({ boeFile, getBOEBlobUrl }: BOEDocumentViewerProps) {
  const blobUrl = getBOEBlobUrl()
  const isPdf = boeFile?.type === "application/pdf" || boeFile?.name?.toLowerCase().endsWith(".pdf")

  return (
    <div className="rounded-lg border border-border overflow-hidden bg-muted/20 h-[780px]">
      {blobUrl && boeFile ? (
        isPdf ? (
          <iframe
            src={blobUrl}
            title={boeFile.name}
            className="w-full h-full border-0"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center overflow-auto p-4">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={blobUrl}
              alt={boeFile.name}
              className="max-w-full max-h-full object-contain rounded"
            />
          </div>
        )
      ) : (
        <div className="w-full h-full flex items-center justify-center">
          <p className="text-sm text-muted-foreground">No BOE document available to preview.</p>
        </div>
      )}
    </div>
  )
}
