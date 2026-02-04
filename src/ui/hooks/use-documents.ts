/**
 * Custom hook for fetching and managing document list with filtering and pagination
 * Uses React Query for caching and automatic refetching
 */

import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { apiClient, type DocumentResponse, type DocumentType, type ExtractionStatus } from "@/lib/api-client"

interface DocumentFilters {
  documentType?: DocumentType | "all"
  status?: ExtractionStatus | "all"
  searchTerm?: string
}

interface DocumentPagination {
  page: number
  pageSize: number
}

interface UseDocumentsOptions {
  initialFilters?: DocumentFilters
  initialPagination?: DocumentPagination
}

export function useDocuments(options: UseDocumentsOptions = {}) {
  const [filters, setFilters] = useState<DocumentFilters>(
    options.initialFilters || {
      documentType: "all",
      status: "complete", // Default to complete documents
      searchTerm: "",
    }
  )

  const [pagination, setPagination] = useState<DocumentPagination>(
    options.initialPagination || {
      page: 1,
      pageSize: 20,
    }
  )

  // React Query for data fetching with caching
  const {
    data: response,
    isLoading,
    error,
    refetch,
    isFetching,
  } = useQuery({
    queryKey: ["documents", filters, pagination],
    queryFn: async () => {
      const result = await apiClient.listDocuments({
        documentType: filters.documentType !== "all" ? filters.documentType : undefined,
        status: filters.status !== "all" ? filters.status : undefined,
        page: pagination.page,
        pageSize: pagination.pageSize,
      })
      return result
    },
    staleTime: 5 * 60 * 1000, // 5 minutes
    refetchOnWindowFocus: true,
    enabled: true,
  })

  // Client-side filtering for search term (if backend doesn't support it)
  const filteredDocuments = response?.data.filter((doc) => {
    if (!filters.searchTerm) return true
    const searchLower = filters.searchTerm.toLowerCase()
    return (
      doc.document_name?.toLowerCase().includes(searchLower) ||
      doc.document_type?.toLowerCase().includes(searchLower)
    )
  })

  const updateFilters = (newFilters: Partial<DocumentFilters>) => {
    setFilters((prev) => ({ ...prev, ...newFilters }))
    // Reset to first page when filters change
    setPagination((prev) => ({ ...prev, page: 1 }))
  }

  const resetFilters = () => {
    setFilters({
      documentType: "all",
      status: "complete",
      searchTerm: "",
    })
    setPagination({ page: 1, pageSize: 20 })
  }

  const goToPage = (page: number) => {
    setPagination((prev) => ({ ...prev, page }))
  }

  const nextPage = () => {
    if (response && response.has_next) {
      goToPage(pagination.page + 1)
    }
  }

  const previousPage = () => {
    if (response && response.has_previous) {
      goToPage(pagination.page - 1)
    }
  }

  return {
    // Data
    documents: filteredDocuments || [],
    totalDocuments: response?.total || 0,
    totalPages: response?.total_pages || 0,

    // Pagination state
    currentPage: pagination.page,
    pageSize: pagination.pageSize,
    hasNextPage: response?.has_next || false,
    hasPreviousPage: response?.has_previous || false,

    // Filter state
    filters,

    // Loading/Error states
    isLoading,
    isFetching,
    error,

    // Actions
    updateFilters,
    resetFilters,
    goToPage,
    nextPage,
    previousPage,
    refetch,
  }
}
