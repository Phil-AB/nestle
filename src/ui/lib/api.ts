/**
 * Legacy API client - kept for backward compatibility
 *
 * Use the new api-client.ts for new code with full TypeScript support
 */

import { apiClient, type UploadResponse, type DocumentResponse, type PaginatedResponse, type ExtractionMode } from './api-client'

// DocumentType is now just a string alias for clarity
type DocumentType = string

export interface Document {
    id: string
    document_number: string
    document_type: string
    extraction_status: "complete" | "incomplete" | "failed"
    items_count: number
    created_at: string
    saved_fields: string[]
    missing_fields: string[]
}

export type { UploadResponse }

export const api = {
    /**
     * Upload a document for extraction
     * @deprecated Use apiClient.uploadDocument instead
     */
    async uploadDocument(
        file: File,
        type?: string,
        options?: {
            documentName?: string
            extractionMode?: ExtractionMode
            shipmentId?: string
        }
    ): Promise<UploadResponse> {
        return apiClient.uploadDocument(file, type, options)
    },

    /**
     * List documents
     * @deprecated Use apiClient.listDocuments instead
     */
    async getDocuments(
        type?: string,
        status?: string,
        page = 1
    ): Promise<{ data: Document[], total: number }> {
        const response = await apiClient.listDocuments({
            documentType: type,
            status: status as any,
            page,
            pageSize: 50
        })

        return {
            data: response.data as unknown as Document[],
            total: response.total
        }
    },

    /**
     * Get document by ID
     */
    async getDocument(id: string, includeRawData = false): Promise<DocumentResponse> {
        return apiClient.getDocument(id, { includeRawData })
    },

    /**
     * Delete document
     */
    async deleteDocument(id: string): Promise<void> {
        return apiClient.deleteDocument(id)
    }
}

// Re-export the new client for direct use
export { apiClient }
