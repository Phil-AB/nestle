"use client"

import { useState, useCallback, useEffect } from "react"
import { useDropzone } from "react-dropzone"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { X, GripVertical, FileText, Upload } from "lucide-react"
import { DndContext, closestCenter, KeyboardSensor, PointerSensor, useSensor, useSensors } from "@dnd-kit/core"
import { arrayMove, SortableContext, sortableKeyboardCoordinates, verticalListSortingStrategy, useSortable } from "@dnd-kit/sortable"
import { CSS } from "@dnd-kit/utilities"

interface FileWithPreview extends File {
  preview?: string
  id: string
}

interface MultiFileUploadProps {
  onFilesChange: (files: File[]) => void
  maxFiles?: number
  acceptedTypes?: { [key: string]: string[] }
}

function SortableFileItem({ file, onRemove }: { file: FileWithPreview; onRemove: () => void }) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: file.id })

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  }

  return (
    <div
      ref={setNodeRef}
      style={style}
      className="flex items-center gap-3 p-3 bg-muted rounded-lg border border-border"
    >
      <div {...attributes} {...listeners} className="cursor-grab active:cursor-grabbing">
        <GripVertical className="w-5 h-5 text-muted-foreground" />
      </div>
      <FileText className="w-6 h-6 text-blue-500 flex-shrink-0" />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium truncate">{file.name}</p>
        <p className="text-xs text-muted-foreground">
          {(file.size / 1024 / 1024).toFixed(2)} MB
        </p>
      </div>
      <Button
        variant="ghost"
        size="sm"
        onClick={onRemove}
        className="flex-shrink-0"
      >
        <X className="w-4 h-4" />
      </Button>
    </div>
  )
}

export default function MultiFileUpload({
  onFilesChange,
  maxFiles = 50,
  acceptedTypes = {
    "application/pdf": [".pdf"],
    "image/*": [".png", ".jpg", ".jpeg", ".tiff"],
  },
}: MultiFileUploadProps) {
  const [files, setFiles] = useState<FileWithPreview[]>([])

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  )

  const onDrop = useCallback((acceptedFiles: File[]) => {
    const newFiles: FileWithPreview[] = acceptedFiles.map((file) =>
      Object.assign(file, {
        id: `${file.name}-${Date.now()}-${Math.random()}`,
      })
    )

    setFiles((prev) => [...prev, ...newFiles].slice(0, maxFiles))
  }, [maxFiles])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: acceptedTypes,
    maxFiles,
  })

  const removeFile = (id: string) => {
    setFiles((prev) => prev.filter((f) => f.id !== id))
  }

  const handleDragEnd = (event: any) => {
    const { active, over } = event

    if (active.id !== over.id) {
      setFiles((items) => {
        const oldIndex = items.findIndex((item) => item.id === active.id)
        const newIndex = items.findIndex((item) => item.id === over.id)

        return arrayMove(items, oldIndex, newIndex)
      })
    }
  }

  // Call onFilesChange whenever files state changes
  useEffect(() => {
    onFilesChange(files)
  }, [files, onFilesChange])

  return (
    <div className="space-y-4">
      {/* Dropzone */}
      <div
        {...getRootProps()}
        className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors
          ${isDragActive ? "border-primary bg-primary/5" : "border-border hover:border-primary/50"}
        `}
      >
        <input {...getInputProps()} />
        <Upload className="w-12 h-12 mx-auto mb-4 text-muted-foreground" />
        {isDragActive ? (
          <p className="text-lg font-medium">Drop the files here...</p>
        ) : (
          <div>
            <p className="text-lg font-medium mb-2">
              Drag and drop files here, or click to select
            </p>
            <p className="text-sm text-muted-foreground">
              Upload up to {maxFiles} files (PDF, PNG, JPG, JPEG, TIFF)
            </p>
          </div>
        )}
      </div>

      {/* File List with Reordering */}
      {files.length > 0 && (
        <Card className="p-4">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold">
              {files.length} {files.length === 1 ? "Page" : "Pages"}
            </h3>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setFiles([])
              }}
            >
              Clear All
            </Button>
          </div>

          <DndContext
            sensors={sensors}
            collisionDetection={closestCenter}
            onDragEnd={handleDragEnd}
          >
            <SortableContext
              items={files.map((f) => f.id)}
              strategy={verticalListSortingStrategy}
            >
              <div className="space-y-2">
                {files.map((file, index) => (
                  <div key={file.id} className="flex items-center gap-2">
                    <span className="text-xs text-muted-foreground font-mono w-8">
                      {index + 1}.
                    </span>
                    <SortableFileItem
                      file={file}
                      onRemove={() => removeFile(file.id)}
                    />
                  </div>
                ))}
              </div>
            </SortableContext>
          </DndContext>

          <p className="text-xs text-muted-foreground mt-4">
            💡 Drag and drop to reorder pages
          </p>
        </Card>
      )}
    </div>
  )
}
