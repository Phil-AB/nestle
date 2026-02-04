/**
 * Document Selector Component
 * Main component for selecting a source document with filtering and pagination
 */

"use client"

import { type DocumentResponse } from "@/lib/api-client"
import { useDocuments } from "@/hooks/use-documents"
import DocumentCard from "@/components/document-card"
import DocumentFilters from "@/components/document-filters"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { ChevronLeft, ChevronRight, FileText, Upload } from "lucide-react"
import Link from "next/link"

interface DocumentSelectorProps {
  onDocumentSelect: (document: DocumentResponse) => void
}

export default function DocumentSelector({ onDocumentSelect }: DocumentSelectorProps) {
  const {
    documents,
    totalDocuments,
    totalPages,
    currentPage,
    hasNextPage,
    hasPreviousPage,
    filters,
    isLoading,
    isFetching,
    updateFilters,
    resetFilters,
    nextPage,
    previousPage,
    goToPage,
  } = useDocuments({
    initialFilters: {
      documentType: "all",
      status: "complete",
      searchTerm: "",
    },
  })

  // Loading skeleton
  if (isLoading) {
    return (
      <div className="space-y-6">
        <Card>
          <CardHeader>
            <Skeleton className="h-8 w-64" />
            <Skeleton className="h-4 w-96 mt-2" />
          </CardHeader>
        </Card>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[...Array(6)].map((_, i) => (
            <Skeleton key={i} className="h-48" />
          ))}
        </div>
      </div>
    )
  }

  // Empty state
  if (documents.length === 0 && !isFetching) {
    return (
      <div className="space-y-6">
        <Card>
          <CardHeader>
            <CardTitle>Select Source Document</CardTitle>
            <CardDescription>
              Choose a document to use as the data source for generation
            </CardDescription>
          </CardHeader>
          <CardContent>
            <DocumentFilters
              filters={filters}
              onFilterChange={updateFilters}
              onReset={resetFilters}
            />
          </CardContent>
        </Card>

        <Card className="p-12">
          <div className="text-center space-y-4">
            <FileText className="w-16 h-16 mx-auto text-muted-foreground" />
            <div>
              <h3 className="text-lg font-semibold">No documents found</h3>
              <p className="text-muted-foreground mt-2">
                {filters.status === "complete"
                  ? "No completed extractions available. Try changing filters or upload a new document."
                  : "No documents match your filters. Try adjusting your search criteria."}
              </p>
            </div>
            <Link href="/upload">
              <Button>
                <Upload className="w-4 h-4 mr-2" />
                Upload Document
              </Button>
            </Link>
          </div>
        </Card>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header with Filters */}
      <Card>
        <CardHeader>
          <CardTitle>Select Source Document</CardTitle>
          <CardDescription>
            Choose a document to use as the data source for generation ({totalDocuments} documents
            available)
          </CardDescription>
        </CardHeader>
        <CardContent>
          <DocumentFilters
            filters={filters}
            onFilterChange={updateFilters}
            onReset={resetFilters}
          />
        </CardContent>
      </Card>

      {/* Document Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {documents.map((document) => (
          <DocumentCard
            key={document.document_id}
            document={document}
            onSelect={() => onDocumentSelect(document)}
          />
        ))}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <Card className="p-4">
          <div className="flex items-center justify-between">
            <div className="text-sm text-muted-foreground">
              Page {currentPage} of {totalPages}
            </div>

            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={previousPage}
                disabled={!hasPreviousPage || isFetching}
              >
                <ChevronLeft className="w-4 h-4 mr-1" />
                Previous
              </Button>

              {/* Page numbers (show current and nearby pages) */}
              <div className="hidden md:flex items-center gap-1">
                {[...Array(totalPages)].map((_, index) => {
                  const pageNumber = index + 1
                  // Show first, last, current, and adjacent pages
                  if (
                    pageNumber === 1 ||
                    pageNumber === totalPages ||
                    Math.abs(pageNumber - currentPage) <= 1
                  ) {
                    return (
                      <Button
                        key={pageNumber}
                        variant={currentPage === pageNumber ? "default" : "outline"}
                        size="sm"
                        onClick={() => goToPage(pageNumber)}
                        disabled={isFetching}
                      >
                        {pageNumber}
                      </Button>
                    )
                  } else if (pageNumber === currentPage - 2 || pageNumber === currentPage + 2) {
                    return (
                      <span key={pageNumber} className="px-2">
                        ...
                      </span>
                    )
                  }
                  return null
                })}
              </div>

              <Button
                variant="outline"
                size="sm"
                onClick={nextPage}
                disabled={!hasNextPage || isFetching}
              >
                Next
                <ChevronRight className="w-4 h-4 ml-1" />
              </Button>
            </div>
          </div>
        </Card>
      )}

      {/* Loading overlay */}
      {isFetching && (
        <div className="fixed bottom-4 right-4">
          <Card className="p-3">
            <div className="flex items-center gap-2 text-sm">
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-primary"></div>
              Refreshing...
            </div>
          </Card>
        </div>
      )}
    </div>
  )
}
