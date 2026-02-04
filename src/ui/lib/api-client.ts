/**
 * API Client for Nestle Document Processing System
 *
 * Complete TypeScript client for interacting with the FastAPI backend.
 */

import { toast } from "sonner"

// API Configuration
// Use relative URLs to leverage Next.js rewrites proxy
// In production, set NEXT_PUBLIC_API_URL to absolute URL if needed
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "/api/v1"
const API_V2_BASE_URL = process.env.NEXT_PUBLIC_API_URL?.replace("/v1", "/v2") || "/api/v2"
const API_KEY = process.env.NEXT_PUBLIC_API_KEY || "dev-key-12345"

// ============================================================================
// Types
// ============================================================================

// Document type info for UI display
export interface DocumentType {
  id: string
  display_name: string
  description: string
  category: string
  icon: string
}

// DocumentType for document processing is now a string - accepts ANY document type
// The system handles all types dynamically
export type DocumentTypeValue = string
export type ExtractionMode = "open" | "focused"
export type ExtractionStatus = "complete" | "incomplete" | "failed" | "processing"
export type ResponseStatus = "success" | "error" | "pending" | "processing"

export interface DocumentMetadata {
  provider: string
  extraction_duration?: number
  confidence?: number
  page_count?: number
  job_id?: string
}

export interface ContentBlock {
  type: string
  content: string
  bbox?: {
    left: number
    top: number
    width: number
    height: number
    page?: number
  }
  page?: number
  confidence?: string
  granular_confidence?: {
    extract_confidence?: number | null
    parse_confidence?: number | null
  }
}

export interface DocumentResponse {
  status: ResponseStatus
  document_id: string
  document_type: string
  document_number?: string
  extraction_status: ExtractionStatus
  extraction_confidence?: number
  fields: Record<string, any>
  items: Array<Record<string, any>>
  blocks?: Array<ContentBlock>  // Raw content blocks for full document rendering
  fields_count: number
  items_count: number
  saved_fields: string[]
  missing_fields: string[]
  metadata?: DocumentMetadata
  layout?: Record<string, any>
  mime_type?: string
  raw_data?: Record<string, any>
  created_at: string
  updated_at?: string
}

export interface UploadResponse {
  status: ResponseStatus
  message: string
  document_id: string
  job_id?: string
  webhook_registered: boolean
}

export interface PaginatedResponse<T> {
  status: ResponseStatus
  data: T[]
  total: number
  page: number
  page_size: number
  total_pages: number
  has_next: boolean
  has_previous: boolean
}

export interface ErrorResponse {
  status: ResponseStatus
  error: string
  message: string
  detail?: string
  timestamp: string
}

export interface ValidationResponse {
  status: ResponseStatus
  validation_id: string
  validation_type: string
  passed: boolean
  accuracy_percentage: number
  total_checks: number
  passed_checks: number
  failed_checks: number
  errors: Array<{
    field: string
    error_type: string
    expected?: any
    actual?: any
    severity: string
  }>
  warnings: any[]
  validated_at: string
}

export interface HealthResponse {
  status: string
  version: string
  environment: string
}

export interface DocumentPage {
  page_id: string
  document_id: string
  page_number: number
  file_path: string
  file_name: string
  file_size: number
  mime_type: string
  extraction_status: string
  extraction_result?: any
  error_message?: string
  created_at: string
  updated_at: string
}

export interface DocumentPagesResponse {
  status: string
  document_id: string
  is_multi_page: boolean
  total_pages: number
  pages: DocumentPage[]
}

export interface RecentActivityItem {
  activity: string
  document_id: string
  document_name?: string
  document_type?: string
  status: string
  created_at: string
}

export interface DocumentStatsData {
  total_documents: number
  extraction_success: number
  documents_generated: number
  pending_documents: number
  by_status: Record<string, number>
  by_type: Record<string, number>
}

export interface DocumentStatsResponse {
  status: ResponseStatus
  data: DocumentStatsData
  recent_activity: RecentActivityItem[]
}

// ============================================================================
// Generation Types (V2 API)
// ============================================================================

export interface GenerationResponse {
  success: boolean
  job_id: string
  status: string
  message: string
  download_url?: string
  generation_time_ms?: number
}

export interface BatchGenerationResponse {
  success: boolean
  batch_id: string
  total: number
  successful: number
  failed: number
  job_ids: string[]
}

export interface GenerationJobStatus {
  job_id: string
  status: string
  created_at: number
  completed_at?: number
  error?: string
}

export interface TemplateMetadata {
  template_id: string
  template_name: string
  template_format: string
  version: string
  template_path: string
  description: string
  required_fields: string[]
  optional_fields: string[]
  supports_tables: boolean
  supports_images: boolean
  created_at: string
  updated_at: string
}

export interface TemplateListResponse {
  templates: TemplateMetadata[]
  total: number
}

export interface RenderersResponse {
  renderers: string[]
  default: string
}

export interface DataProvidersResponse {
  providers: string[]
  default: string
}

export interface GenerationHealthResponse {
  status: string
  renderers: Record<string, boolean>
  data_providers: Record<string, boolean>
  templates_loaded: number
  job_storage_type: string
}

// ============================================================================
// Population Types (V2 API)
// ============================================================================

export interface FormMetadata {
  form_id: string
  form_name: string
  description: string
  template_path: string
  field_count: number
  required_document_types?: string[]
  created_at: string
  updated_at: string
}

export interface FormListResponse {
  status: string
  forms: FormMetadata[]
  total: number
}

export interface PopulationResponse {
  success: boolean
  form_id: string
  output_path?: string
  metadata?: {
    document_ids: string[]
    field_count: number
    merge_strategy: string
    options: Record<string, any>
  }
  error?: string
}

// ============================================================================
// Universal Insights Types (100% config-driven, dynamic)
// ============================================================================

/**
 * Customer profile - 100% dynamic, fields from use case config
 */
export interface CustomerProfile {
  [key: string]: any
}

/**
 * Risk factor scoring breakdown
 */
export interface RiskFactorScoring {
  factor_name: string
  score: number
  weight: number
  weighted_score: number
  confidence: number
  reasoning: string
  data_points: string[]
}

/**
 * Risk assessment - includes rule-based scores and LLM reasoning
 */
export interface RiskAssessment {
  risk_score: number
  risk_level: string
  creditworthiness: string
  scoring_breakdown: RiskFactorScoring[]
  factors: {
    positive: string[]
    concerns: string[]
  }
  reasoning: string
  calculation_summary: string
  // LLM-enhanced fields
  detailed_reasoning?: string
  reasoning_source?: string
  [key: string]: any
}

/**
 * Product eligibility - dynamic products from config
 */
export interface ProductEligibility {
  [productId: string]: {
    eligible: boolean
    product_name?: string
    max_amount?: number
    recommended_amount?: number
    interest_rate?: number
    term_months?: number
    reason?: string
    [key: string]: any
  }
}

/**
 * Automated decisions - dynamic from config
 */
export interface AutomatedDecision {
  decision?: string
  value?: any
  rule_name?: string
  message?: string
  confidence: number
  [key: string]: any
}

/**
 * Insights metadata
 */
export interface InsightsMetadata {
  generated_at: string
  processing_time_seconds: number
  engine: string
  scoring?: string
  reasoning?: string
  config_version?: {
    field_mapping?: string
    criteria?: string
  }
  [key: string]: any
}

/**
 * Universal insights response - structure from use case config
 */
export interface InsightsResponse {
  success: boolean
  document_id: string
  use_case_id: string
  customer_profile: CustomerProfile
  risk_assessment: RiskAssessment
  product_eligibility: ProductEligibility
  recommendations: Record<string, any>
  automated_decisions: Record<string, AutomatedDecision>
  metadata: InsightsMetadata
  pdf_path?: string
  error?: string
}

/**
 * Document list item for insights UI
 */
export interface DocumentListItem {
  document_id: string
  display_name: string
  document_type?: string
  created_at: string
  summary: Record<string, any>
}

/**
 * Insights health response
 */
export interface InsightsHealthResponse {
  status: string
  service: string
  version: string
  capabilities: string[]
}

// ============================================================================
// Document Profile Types (V2 API)
// ============================================================================

export type DocumentFormType = "handwritten" | "digital" | "unknown"
export type DocumentRiskLevel = "high" | "medium" | "low" | "unknown"

export interface DocumentProfile {
  document_id: string
  name: string
  document_type?: string
  form_type: DocumentFormType
  risk_level?: DocumentRiskLevel
  risk_score?: number
  display_order?: number
  tags: string[]
  created_at?: string
}

export interface DocumentProfileListResponse {
  profiles: DocumentProfile[]
  total: number
}

export interface ProfileUpdateResponse {
  success: boolean
  message: string
  document_id?: string
  updated_count?: number
}

export interface ProfileStatsResponse {
  total_with_profiles: number
  by_form_type: Record<string, number>
  by_risk_level: Record<string, number>
}

// ============================================================================
// Universal Analytics Types (V2 API) - 100% Config-Driven
// ============================================================================

export type DateRange = "30d" | "90d" | "12m" | "all"

/**
 * Use case information
 */
export interface AnalyticsUseCase {
  use_case_id: string
  name: string
  description?: string
}

/**
 * Universal trend data point - dynamic metrics
 */
export interface TrendDataPoint {
  period: string
  count: number
  [metricKey: string]: any  // Dynamic metrics from config (e.g., average_risk_score)
}

/**
 * Range-based dimension distribution
 */
export interface RangeDistributionItem {
  label: string
  min?: number
  max?: number
  count: number
  percentage?: number
}

/**
 * Value-based dimension distribution
 */
export interface ValueDistributionItem {
  value: string
  count: number
  percentage?: number
}

/**
 * Universal dimension data - can be range-based or value-based
 */
export type DimensionData = Record<string, number> | RangeDistributionItem[] | ValueDistributionItem[]

/**
 * Product eligibility info
 */
export interface ProductEligibilityInfo {
  eligible: number
  total: number
  percentage: number
  product_name?: string
}

/**
 * Products data - dynamic product types from config
 */
export type ProductsData = Record<string, ProductEligibilityInfo | number>

/**
 * Analytics metadata
 */
export interface AnalyticsMetadata {
  generated_at: string
  processing_time_seconds: number
  date_range: string
  filters_applied?: Record<string, any>
}

/**
 * Universal analytics response - 100% dynamic based on use case config
 */
export interface AnalyticsResponse {
  success: boolean
  use_case_id: string
  overview: Record<string, any>           // Dynamic overview metrics from config
  dimensions: Record<string, DimensionData>  // Dynamic dimension breakdowns from config
  trends: TrendDataPoint[]                 // Time-series trend data
  products: ProductsData                   // Dynamic product eligibility from config
  metadata: AnalyticsMetadata
  error?: string
}

/**
 * Use case configuration info
 */
export interface UseCaseConfig {
  use_case_id: string
  name: string
  description?: string
  version?: string
  overview_metrics?: string[]     // List of metric IDs
  dimensions?: string[]            // List of dimension IDs
  trend_metrics?: string[]        // List of trend metric IDs
  products?: string[]             // List of product IDs
}

/**
 * Use cases list response
 */
export interface UseCasesListResponse {
  use_cases: UseCaseConfig[]
  default_use_case: string
  total: number
}

/**
 * Metric configuration from backend
 */
export interface MetricConfig {
  name: string
  description?: string
  aggregation: "count" | "average" | "sum" | "percentage" | "count_where"
  source: {
    type: "metadata" | "field"
    field: string
  }
  decimals?: number
  default?: any
  condition?: Record<string, any>
}

/**
 * Dimension configuration from backend
 */
export interface DimensionConfig {
  name: string
  description?: string
  source: {
    type: "metadata" | "field"
    field: string
  }
  aggregation: "count_by_value" | "distribution" | "value_mapping"
  ranges?: Array<{
    label: string
    min?: number
    max?: number
  }>
  value_map?: Record<string, string[]>
  display_order?: number
}

/**
 * Product configuration from backend
 */
export interface ProductConfig {
  name: string
  eligibility_conditions: Array<{
    source: {
      type: "metadata" | "field"
      field: string
    }
    operator: string
    value: any
  }>
}

/**
 * Full analytics configuration response from backend
 */
export interface AnalyticsConfigResponse {
  success: boolean
  use_case_id: string
  config: {
    metrics?: {
      use_case_id: string
      version?: string
      overview_metrics?: Record<string, MetricConfig>
      trends?: {
        period?: string
        default_periods?: number
        metrics?: Record<string, MetricConfig>
      }
      products?: Record<string, ProductConfig>
      comparison_metrics?: Record<string, MetricConfig>
    }
    dimensions?: {
      use_case_id: string
      version?: string
      dimensions?: Record<string, DimensionConfig>
      dimension_groups?: Record<string, {
        name: string
        dimensions: string[]
      }>
    }
  }
}

/**
 * Percentile comparisons for a document
 */
export interface PercentileComparison {
  [metricKey: string]: number | undefined
  total_compared: number
}

/**
 * Health response for analytics module
 */
export interface AnalyticsHealthResponse {
  status: string
  service: string
  version: string
  use_cases_loaded: number
  default_use_case: string
}

// ============================================================================
// Legacy Types (for backward compatibility during transition)
// ============================================================================

/**
 * @deprecated Use AnalyticsResponse.overview instead - this is loan-specific
 */
export interface OverviewMetrics {
  total_applications: number
  average_risk_score: number
  average_monthly_income: number
  eligibility_rate: number
  trend: {
    applications_change_percent: number
    applications_direction: string
  }
}

/**
 * @deprecated Use AnalyticsResponse.dimensions instead - this is loan-specific
 */
export interface DemographicsBreakdown {
  age_distribution: Array<{ range: string; count: number; percentage: number }>
  employment_breakdown: Record<string, number>
  gender_breakdown: Record<string, number>
  income_distribution: Array<{ range: string; min_value: number; max_value: number; count: number }>
  risk_distribution: Record<string, number>
}

/**
 * @deprecated Use AnalyticsResponse.products instead - this is loan-specific
 */
export interface ProductInsights {
  form_type_breakdown: Record<string, number>
  product_eligibility: {
    extra_cash: { eligible: number; total: number; percentage: number }
    extra_balance: { eligible: number; total: number; percentage: number }
    credit_card: { eligible: number; total: number; percentage: number }
  }
}

/**
 * @deprecated Use AnalyticsResponse.trends instead
 */
export interface MonthlyTrendData {
  month: string
  count: number
  average_risk_score?: number
}

/**
 * @deprecated Use AnalyticsResponse directly
 */
export interface DashboardData {
  overview: OverviewMetrics
  demographics: DemographicsBreakdown
  products: ProductInsights
  monthly_trends: MonthlyTrendData[]
  generated_at: string
}

// ============================================================================
// Pre-Loan Integration Types (V2 API)
// ============================================================================

export type PreLoanStatus = "eligible" | "discuss_with_officer" | "not_eligible"

export interface PreLoanDataRequest {
  document_id: string
  session_id: string
  pre_loan_status: PreLoanStatus
  pre_loan_date: string
  answers: Record<string, any>
  risk_assessment?: PreLoanRiskAssessment
}

export interface PreLoanRiskAssessment {
  pre_score?: number
  factors?: string[]
}

export interface PreLoanSessionCreateRequest {
  answers: Record<string, any>
  pre_loan_status: PreLoanStatus
  risk_assessment?: PreLoanRiskAssessment
}

export interface DocumentLinkRequest {
  session_id: string
  document_id: string
}

export interface PreLoanStatusResponse {
  document_id: string
  customer_name: string
  pre_loan_status: PreLoanStatus | null
  pre_loan_date: string | null
  session_id: string | null
  created_at: string | null
}

export interface PreLoanListResponse {
  documents: PreLoanStatusResponse[]
  total: number
}

export interface CombinedAssessmentResponse {
  document_id: string
  pre_loan_status: PreLoanStatus | null
  pre_loan_risk_score: number | null
  insights_risk_score: number | null
  combined_status: string
  pre_loan_date: string | null
  session_id: string | null
}

export interface SessionCreateResponse {
  session_id: string
  expires_at: string
  document_id?: string
}

export interface SessionDataResponse {
  session_id: string
  status: string
  pre_loan_status: PreLoanStatus
  answers: Record<string, any>
  risk_assessment?: PreLoanRiskAssessment
  created_at: string
  expires_at: string
  document_id?: string
}

export interface IntegrationStatusResponse {
  service: string
  version: string
  capabilities: string[]
  active_sessions: number
}

// ============================================================================
// Automation Types (V2 API)
// ============================================================================

export type AutomationTriggerEvent = "insights_generated" | "manual" | "webhook" | "batch" | "scheduled"

export interface AutomationTriggerRequest {
  document_id: string
  trigger_event: AutomationTriggerEvent
  trigger_data?: Record<string, any>
}

export interface AutomationTriggerResponse {
  success: boolean
  message: string
  document_id: string
  action_taken?: string
  metadata?: {
    eligibility?: { eligible: boolean; criteria: Record<string, boolean>; risk_score?: number }
    email_sent?: boolean
    letter_generated?: boolean
    customer_data?: { name?: string; risk_score?: number }
    trigger_event?: string
  }
}

export interface BatchAutomationRequest {
  document_ids: string[]
  trigger_event: "batch" | "scheduled"
}

export interface BatchAutomationResponse {
  success: boolean
  total: number
  processed: number
  approved: number
  skipped: number
  failed: number
  results: Array<{
    document_id: string
    success: boolean
    action_taken?: string
    error?: string
  }>
}

export interface AutomationStatusResponse {
  document_id: string
  approval_status?: string
  auto_approved: boolean
  approved_at?: string
  risk_score?: number
  email_sent: boolean
  letter_generated: boolean
}

export interface AutomationConfigResponse {
  enabled: boolean
  risk_threshold: number
  require_pre_loan_eligible: boolean
  require_email: boolean
  agent_config: {
    agent_type: string
    llm_provider: string
    llm_model: string
    temperature?: number
  }
}

export interface EligibleDocument {
  document_id: string
  customer_name: string
  risk_score: number
  risk_level: string
  created_at: string
  already_processed: boolean
}

export interface EligibleDocumentsResponse {
  total: number
  documents: EligibleDocument[]
}

// ============================================================================
// API Client Class
// ============================================================================

class APIClient {
  private baseURL: string
  private baseURLV2: string
  private apiKey: string

  constructor(baseURL: string = API_BASE_URL, apiKey: string = API_KEY) {
    this.baseURL = baseURL
    this.baseURLV2 = baseURL.replace("/v1", "/v2")
    this.apiKey = apiKey
  }

  /**
   * Make HTTP request with proper headers and error handling
   */
  private async request<T>(
    endpoint: string,
    options: RequestInit = {},
    useV2 = false
  ): Promise<T> {
    const baseUrl = useV2 ? this.baseURLV2 : this.baseURL
    const url = endpoint.startsWith('http') ? endpoint : `${baseUrl}${endpoint}`

    // Build headers with proper typing
    const headers: Record<string, string> = {
      "X-API-Key": this.apiKey,
    }

    // Merge with existing headers
    const existingHeaders = options.headers as Record<string, string> | undefined
    if (existingHeaders) {
      Object.assign(headers, existingHeaders)
    }

    // Don't set Content-Type for FormData (browser will set it with boundary)
    if (!(options.body instanceof FormData)) {
      headers["Content-Type"] = "application/json"
    }

    // Log request details for debugging
    console.log('Making API request:', {
      method: options.method || 'GET',
      url: url,
      headers: { ...headers, 'X-API-Key': headers['X-API-Key'] ? '[REDACTED]' : 'MISSING' },
      hasBody: !!options.body
    })

    try {
      const response = await fetch(url, {
        ...options,
        headers,
      })

      // Handle non-JSON responses
      const contentType = response.headers.get("content-type")
      const isJSON = contentType?.includes("application/json")

      if (!response.ok) {
        if (isJSON) {
          const error: ErrorResponse = await response.json()
          console.error('API Error Details:', {
            status: response.status,
            statusText: response.statusText,
            url: url,
            error: error
          })
          throw new Error(error.message || error.error || `API request failed: ${response.status}`)
        } else {
          const errorText = await response.text()
          console.error('Non-JSON API Error:', {
            status: response.status,
            statusText: response.statusText,
            url: url,
            response: errorText
          })
          throw new Error(`HTTP ${response.status}: ${response.statusText}`)
        }
      }

      if (response.status === 204) {
        return {} as T
      }

      return isJSON ? await response.json() : ({} as T)
    } catch (error) {
      console.error("API Error:", error)
      if (error instanceof Error) {
        toast.error(error.message)
      }
      throw error
    }
  }

  // ========================================================================
  // Documents Endpoints
  // ========================================================================

  /**
   * Upload a document for extraction
   */
  async uploadDocument(
    file: File,
    documentType?: DocumentTypeValue,
    options?: {
      extractionMode?: ExtractionMode
      shipmentId?: string
      webhookUrl?: string
      documentName?: string
    }
  ): Promise<UploadResponse> {
    const formData = new FormData()
    formData.append("file", file)

    const params = new URLSearchParams({
      extraction_mode: options?.extractionMode || "focused",
    })

    if (documentType) {
      params.append("document_type", documentType)
    }

    if (options?.documentName) {
      params.append("document_name", options.documentName)
    }

    if (options?.shipmentId) {
      params.append("shipment_id", options.shipmentId)
    }

    if (options?.webhookUrl) {
      params.append("webhook_url", options.webhookUrl)
    }

    return this.request<UploadResponse>(
      `/documents/upload?${params.toString()}`,
      {
        method: "POST",
        body: formData,
      }
    )
  }

  /**
   * Upload multiple files as a multi-page document
   */
  async uploadMultiPageDocument(
    files: File[],
    documentType: DocumentTypeValue,
    options?: {
      extractionMode?: ExtractionMode
      webhookUrl?: string
    }
  ): Promise<UploadResponse> {
    const formData = new FormData()

    // Append all files
    files.forEach((file) => {
      formData.append("files", file)
    })

    const params = new URLSearchParams({
      document_type: documentType,
      extraction_mode: options?.extractionMode || "focused",
    })

    if (options?.webhookUrl) {
      params.append("webhook_url", options.webhookUrl)
    }

    return this.request<UploadResponse>(
      `/documents/multi-page?${params.toString()}`,
      {
        method: "POST",
        body: formData,
      }
    )
  }

  /**
   * Get a document by ID
   */
  async getDocument(
    documentId: string,
    options?: {
      includeRawData?: boolean
      includeLayout?: boolean
    }
  ): Promise<DocumentResponse> {
    const params = new URLSearchParams()

    if (options?.includeRawData) {
      params.append("include_raw_data", "true")
    }

    if (options?.includeLayout) {
      params.append("include_layout", "true")
    }

    const query = params.toString()
    return this.request<DocumentResponse>(
      `/documents/${documentId}${query ? `?${query}` : ""}`
    )
  }

  /**
   * List documents with pagination and filters
   */
  async listDocuments(options?: {
    documentType?: DocumentTypeValue
    status?: ExtractionStatus
    page?: number
    pageSize?: number
  }): Promise<PaginatedResponse<DocumentResponse>> {
    const params = new URLSearchParams()

    if (options?.documentType) {
      params.append("document_type", options.documentType)
    }

    if (options?.status) {
      params.append("status", options.status)
    }

    params.append("page", String(options?.page || 1))
    params.append("page_size", String(options?.pageSize || 50))

    return this.request<PaginatedResponse<DocumentResponse>>(
      `/documents/?${params.toString()}`
    )
  }

  /**
   * Update document field values
   */
  async updateDocumentFields(
    documentId: string,
    fieldUpdates: Record<string, any>,
    updateMetadata?: Record<string, any>
  ): Promise<DocumentResponse> {
    return this.request<DocumentResponse>(
      `/documents/${documentId}/fields`,
      {
        method: "PATCH",
        body: JSON.stringify({
          field_updates: fieldUpdates,
          update_metadata: updateMetadata,
        }),
      }
    )
  }

  /**
   * Approve a document and save it to the database
   */
  async approveDocument(
    documentId: string,
    approvalData: Record<string, any>
  ): Promise<DocumentResponse> {
    return this.request<DocumentResponse>(
      `/documents/${documentId}/approve`,
      {
        method: "POST",
        body: JSON.stringify(approvalData),
      }
    )
  }

  /**
   * Delete a document
   */
  async deleteDocument(documentId: string): Promise<void> {
    await this.request<void>(`/documents/${documentId}`, {
      method: "DELETE",
    })
  }

  /**
   * Get all pages for a multi-page document
   */
  async getDocumentPages(documentId: string): Promise<DocumentPagesResponse> {
    return this.request<DocumentPagesResponse>(`/documents/${documentId}/pages`)
  }

  /**
   * Reorder pages in a multi-page document
   */
  async reorderDocumentPages(
    documentId: string,
    pageOrder: string[]
  ): Promise<{ success: boolean; message: string }> {
    return this.request<{ success: boolean; message: string }>(
      `/documents/${documentId}/pages/reorder`,
      {
        method: "PUT",
        body: JSON.stringify({ page_order: pageOrder }),
      }
    )
  }

  /**
   * Download a specific page from a multi-page document
   */
  async downloadPage(documentId: string, pageNumber: number): Promise<Blob> {
    const response = await fetch(
      `${this.baseURL}/documents/${documentId}/pages/${pageNumber}/file`,
      {
        headers: {
          "X-API-Key": this.apiKey,
        },
      }
    )

    if (!response.ok) {
      throw new Error(`Failed to download page: ${response.statusText}`)
    }

    return response.blob()
  }

  // ========================================================================
  // Health & Status
  // ========================================================================

  /**
   * Check API health
   */
  async healthCheck(): Promise<HealthResponse> {
    // Health endpoint doesn't require auth
    const response = await fetch(`${this.baseURL.replace("/api/v1", "")}/health`)
    return response.json()
  }

  /**
   * Get API root info
   */
  async getAPIInfo(): Promise<{
    name: string
    version: string
    docs: string
    health: string
    api: string
  }> {
    const response = await fetch(this.baseURL.replace("/api/v1", "/"))
    return response.json()
  }

  /**
   * Get URL for original document file
   * Uses relative URL to leverage Next.js proxy
   */
  getDocumentFileUrl(documentId: string): string {
    // Use relative URL which will be proxied through Next.js to backend
    return `/api/documents/${documentId}/file`
  }

  /**
   * Get document file with authentication
   */
  async getDocumentFile(documentId: string): Promise<Blob> {
    const response = await fetch(this.getDocumentFileUrl(documentId), {
      headers: {
        "X-API-Key": this.apiKey,
      },
    })

    if (!response.ok) {
      throw new Error(`Failed to fetch document file: ${response.statusText}`)
    }

    return response.blob()
  }

  /**
   * Get document statistics for dashboard
   */
  async getDocumentStats(): Promise<DocumentStatsResponse> {
    return this.request<DocumentStatsResponse>("/documents/stats")
  }

  // ========================================================================
  // Generation Endpoints (V2 API)
  // ========================================================================

  // ========================================================================
  // Generation Endpoints (V2 API)
  // ========================================================================

  /**
   * Generate a document from template and data
   */
  async generateDocument(
    templateId: string,
    dataSource: {
      provider: string
      query: Record<string, any>
      merge_strategy?: string  // For multi-source: 'prioritized', 'best_available', 'all_required'
      options?: Record<string, any>
    },
    mappingId?: string,
    options?: Record<string, any>
  ): Promise<GenerationResponse> {
    return this.request<GenerationResponse>(
      "/generation/generate",
      {
        method: "POST",
        body: JSON.stringify({
          template_id: templateId,
          data_source: dataSource,
          mapping_id: mappingId,
          options,
        }),
      },
      true // Use V2 API
    )
  }

  /**
   * Generate a document from multiple source documents (multi-source mode)
   */
  async generateMultiSourceDocument(
    templateId: string,
    documentIds: string[],
    mergeStrategy: "prioritized" | "best_available" | "all_required" = "prioritized",
    mappingId?: string,
    options?: Record<string, any>
  ): Promise<GenerationResponse> {
    return this.generateDocument(
      templateId,
      {
        provider: "postgres",
        query: { document_ids: documentIds },
        merge_strategy: mergeStrategy,
      },
      mappingId,
      options
    )
  }

  /**
   * Generate multiple documents in batch
   */
  async generateBatch(
    templateId: string,
    dataSources: Array<{
      provider: string
      query: Record<string, any>
      options?: Record<string, any>
    }>,
    mappingId?: string,
    options?: Record<string, any>
  ): Promise<BatchGenerationResponse> {
    return this.request<BatchGenerationResponse>(
      "/generation/batch",
      {
        method: "POST",
        body: JSON.stringify({
          template_id: templateId,
          data_sources: dataSources,
          mapping_id: mappingId,
          options,
        }),
      },
      true
    )
  }

  /**
   * Get generation job status
   */
  async getGenerationJobStatus(jobId: string): Promise<GenerationJobStatus> {
    return this.request<GenerationJobStatus>(
      `/generation/jobs/${jobId}`,
      {},
      true
    )
  }

  /**
   * Download generated document
   */
  async downloadGeneratedDocument(jobId: string): Promise<Blob> {
    const response = await fetch(
      `${this.baseURLV2}/generation/download/${jobId}`,
      {
        headers: {
          "X-API-Key": this.apiKey,
        },
      }
    )

    if (!response.ok) {
      throw new Error(`Failed to download document: ${response.statusText}`)
    }

    return response.blob()
  }

  /**
   * List available templates
   */
  async listTemplates(format?: string): Promise<TemplateListResponse> {
    const params = new URLSearchParams()
    if (format) {
      params.append("format", format)
    }

    return this.request<TemplateListResponse>(
      `/generation/templates${params.toString() ? `?${params.toString()}` : ""}`,
      {},
      true
    )
  }

  /**
   * Get template details
   */
  async getTemplateDetails(templateId: string): Promise<TemplateMetadata> {
    return this.request<TemplateMetadata>(
      `/generation/templates/${templateId}`,
      {},
      true
    )
  }

  /**
   * List available renderers
   */
  async listRenderers(): Promise<RenderersResponse> {
    return this.request<RenderersResponse>("/generation/renderers", {}, true)
  }

  /**
   * List available data providers
   */
  async listDataProviders(): Promise<DataProvidersResponse> {
    return this.request<DataProvidersResponse>("/generation/data-providers", {}, true)
  }

  /**
   * Check generation module health
   */
  async generationHealthCheck(): Promise<GenerationHealthResponse> {
    return this.request<GenerationHealthResponse>("/generation/health", {}, true)
  }

  /**
   * Get available document types
   */
  async getDocumentTypes(): Promise<{ types: DocumentType[], categories: string[] }> {
    const url = `${this.baseURL}/documents/document-types`
    console.log('Fetching document types from:', url)
    console.log('Using API key:', this.apiKey ? 'provided' : 'missing')
    return this.request("/documents/document-types")
  }

  // ========================================================================
  // Population Endpoints (V2 API)
  // ========================================================================

  /**
   * List available fillable forms
   */
  async listForms(): Promise<FormMetadata[]> {
    return this.request<FormMetadata[]>(
      "/population/forms",
      { method: "GET" },
      true // Use V2 API
    )
  }

  /**
   * Populate a fillable form with document data
   */
  async populateForm(
    formId: string,
    documentIds: string[],
    options?: {
      mergeStrategy?: "prioritized" | "best_available" | "combine"
      flattenForm?: boolean
    }
  ): Promise<PopulationResponse> {
    return this.request<PopulationResponse>(
      "/population/populate",
      {
        method: "POST",
        body: JSON.stringify({
          form_id: formId,
          document_ids: documentIds,
          merge_strategy: options?.mergeStrategy || "best_available",
          flatten_form: options?.flattenForm || false
        })
      },
      true // Use V2 API
    )
  }

  /**
   * Download populated form
   */
  async downloadPopulatedForm(outputPath: string): Promise<Blob> {
    // The output_path from population response is a full file path
    // We need to construct the download URL
    const response = await fetch(outputPath, {
      headers: {
        "X-API-Key": this.apiKey,
      },
    })

    if (!response.ok) {
      throw new Error(`Failed to download populated form: ${response.statusText}`)
    }

    return response.blob()
  }

  // ========================================================================
  // Banking Insights Endpoints (V2 API)
  // ========================================================================

  /**
   * Generate insights for a document
   */
  async generateInsights(
    documentId: string,
    includePdf = true,
    useCaseId = "forms-capital-loan"
  ): Promise<InsightsResponse> {
    return this.request<InsightsResponse>(
      "/insights/generate",
      {
        method: "POST",
        body: JSON.stringify({
          document_id: documentId,
          use_case_id: useCaseId,
          include_pdf: includePdf,
          output_format: "pdf"
        })
      },
      true // Use V2 API
    )
  }

  /**
   * List documents for insights generation
   */
  async listInsightsDocuments(limit = 50, offset = 0, useCaseId?: string): Promise<DocumentListItem[]> {
    const params = new URLSearchParams({ limit: limit.toString(), offset: offset.toString() })
    if (useCaseId) {
      params.append("use_case_id", useCaseId)
    }
    return this.request<DocumentListItem[]>(
      `/insights/documents?${params}`,
      { method: "GET" },
      true // Use V2 API
    )
  }

  /**
   * Download insights PDF
   */
  async downloadInsightsPdf(filename: string): Promise<Blob> {
    const url = `${this.baseURLV2}/insights/download/${filename}`
    const response = await fetch(url, {
      headers: {
        "X-API-Key": this.apiKey,
      },
    })

    if (!response.ok) {
      throw new Error(`Failed to download insights PDF: ${response.statusText}`)
    }

    return response.blob()
  }

  /**
   * Check insights module health
   */
  async insightsHealthCheck(): Promise<InsightsHealthResponse> {
    return this.request<InsightsHealthResponse>("/insights/health", { method: "GET" }, true)
  }

  // ========================================================================
  // Document Profile Management Endpoints (V2 API)
  // ========================================================================

  /**
   * List document profiles with optional filtering
   */
  async listDocumentProfiles(options?: {
    form_type?: DocumentFormType
    risk_level?: DocumentRiskLevel
    tag?: string
    has_insights?: boolean
    limit?: number
    offset?: number
  }): Promise<DocumentProfileListResponse> {
    const params = new URLSearchParams()

    if (options?.form_type) params.append("form_type", options.form_type)
    if (options?.risk_level) params.append("risk_level", options.risk_level)
    if (options?.tag) params.append("tag", options.tag)
    if (options?.has_insights !== undefined) params.append("has_insights", String(options.has_insights))
    params.append("limit", String(options?.limit || 100))
    params.append("offset", String(options?.offset || 0))

    return this.request<DocumentProfileListResponse>(
      `/profiles?${params}`,
      { method: "GET" },
      true
    )
  }

  /**
   * Set document form type
   */
  async setDocumentFormType(documentId: string, formType: DocumentFormType): Promise<ProfileUpdateResponse> {
    return this.request<ProfileUpdateResponse>(
      "/profiles/form-type",
      {
        method: "POST",
        body: JSON.stringify({
          document_id: documentId,
          form_type: formType
        })
      },
      true
    )
  }

  /**
   * Set document risk level
   */
  async setDocumentRiskLevel(
    documentId: string,
    riskLevel: DocumentRiskLevel,
    riskScore?: number
  ): Promise<ProfileUpdateResponse> {
    return this.request<ProfileUpdateResponse>(
      "/profiles/risk-level",
      {
        method: "POST",
        body: JSON.stringify({
          document_id: documentId,
          risk_level: riskLevel,
          risk_score: riskScore
        })
      },
      true
    )
  }

  /**
   * Set document display order
   */
  async setDocumentDisplayOrder(documentId: string, order: number): Promise<ProfileUpdateResponse> {
    return this.request<ProfileUpdateResponse>(
      "/profiles/display-order",
      {
        method: "POST",
        body: JSON.stringify({
          document_id: documentId,
          order: order
        })
      },
      true
    )
  }

  /**
   * Set document profile tags
   */
  async setDocumentProfileTags(documentId: string, tags: string[]): Promise<ProfileUpdateResponse> {
    return this.request<ProfileUpdateResponse>(
      "/profiles/tags",
      {
        method: "POST",
        body: JSON.stringify({
          document_id: documentId,
          tags: tags
        })
      },
      true
    )
  }

  /**
   * Bulk update form types for multiple documents
   */
  async bulkUpdateFormTypes(documentIds: string[], formType: DocumentFormType): Promise<ProfileUpdateResponse> {
    return this.request<ProfileUpdateResponse>(
      "/profiles/bulk/form-type",
      {
        method: "POST",
        body: JSON.stringify({
          document_ids: documentIds,
          form_type: formType
        })
      },
      true
    )
  }

  /**
   * Get profile statistics
   */
  async getProfileStats(): Promise<ProfileStatsResponse> {
    return this.request<ProfileStatsResponse>(
      "/profiles/stats",
      { method: "GET" },
      true
    )
  }

  /**
   * Clear profile metadata from a document
   */
  async clearProfileMetadata(documentId: string): Promise<ProfileUpdateResponse> {
    return this.request<ProfileUpdateResponse>(
      `/profiles/${documentId}`,
      { method: "DELETE" },
      true
    )
  }

  // ========================================================================
  // Universal Analytics Endpoints (V2 API) - 100% Config-Driven
  // ========================================================================

  /**
   * Get complete dashboard data for a use case (primary method)
   * This is the main endpoint for fetching analytics data
   */
  async getAnalytics(
    dateRange?: DateRange,
    useCaseId = "forms-capital-loan"
  ): Promise<AnalyticsResponse> {
    const params = new URLSearchParams()
    if (dateRange) params.append("date_range", dateRange)
    params.append("use_case_id", useCaseId)

    return this.request<AnalyticsResponse>(
      `/analytics/dashboard${params ? `?${params}` : ""}`,
      { method: "GET" },
      true
    )
  }

  /**
   * Get overview metrics only
   */
  async getOverviewMetrics(
    dateRange?: DateRange,
    useCaseId = "forms-capital-loan"
  ): Promise<Record<string, any>> {
    const params = new URLSearchParams()
    if (dateRange) params.append("date_range", dateRange)
    params.append("use_case_id", useCaseId)

    return this.request<Record<string, any>>(
      `/analytics/overview${params ? `?${params}` : ""}`,
      { method: "GET" },
      true
    )
  }

  /**
   * Get all dimension breakdowns
   */
  async getDimensions(
    dateRange?: DateRange,
    useCaseId = "forms-capital-loan"
  ): Promise<Record<string, DimensionData>> {
    const params = new URLSearchParams()
    if (dateRange) params.append("date_range", dateRange)
    params.append("use_case_id", useCaseId)

    return this.request<Record<string, DimensionData>>(
      `/analytics/dimensions${params ? `?${params}` : ""}`,
      { method: "GET" },
      true
    )
  }

  /**
   * Get a specific dimension breakdown
   */
  async getDimension(
    dimensionId: string,
    dateRange?: DateRange,
    useCaseId = "forms-capital-loan"
  ): Promise<DimensionData> {
    const params = new URLSearchParams()
    if (dateRange) params.append("date_range", dateRange)
    params.append("use_case_id", useCaseId)

    return this.request<DimensionData>(
      `/analytics/dimensions/${dimensionId}${params ? `?${params}` : ""}`,
      { method: "GET" },
      true
    )
  }

  /**
   * Get trend data
   */
  async getTrends(
    periods = 12,
    useCaseId = "forms-capital-loan"
  ): Promise<TrendDataPoint[]> {
    return this.request<TrendDataPoint[]>(
      `/analytics/trends?use_case_id=${useCaseId}&periods=${periods}`,
      { method: "GET" },
      true
    )
  }

  /**
   * Get products eligibility data
   */
  async getProducts(
    useCaseId = "forms-capital-loan"
  ): Promise<ProductsData> {
    return this.request<ProductsData>(
      `/analytics/products?use_case_id=${useCaseId}`,
      { method: "GET" },
      true
    )
  }

  /**
   * Get percentile comparisons for a document
   */
  async getPercentileComparisons(
    documentId: string,
    useCaseId = "forms-capital-loan"
  ): Promise<PercentileComparison> {
    return this.request<PercentileComparison>(
      `/analytics/percentile/${documentId}?use_case_id=${useCaseId}`,
      { method: "GET" },
      true
    )
  }

  /**
   * List available use cases
   */
  async listAnalyticsUseCases(): Promise<UseCasesListResponse> {
    return this.request<UseCasesListResponse>(
      "/analytics/use-cases",
      { method: "GET" },
      true
    )
  }

  /**
   * Get analytics health status
   */
  async getAnalyticsHealth(): Promise<AnalyticsHealthResponse> {
    return this.request<AnalyticsHealthResponse>(
      "/analytics/health",
      { method: "GET" },
      true
    )
  }

  /**
   * Get analytics configuration for a specific use case
   * Returns the full metrics and dimensions configuration
   */
  async getAnalyticsConfig(useCaseId: string): Promise<AnalyticsConfigResponse> {
    return this.request<AnalyticsConfigResponse>(
      `/analytics/config/${useCaseId}`,
      { method: "GET" },
      true
    )
  }

  // ========================================================================
  // Legacy Analytics Methods (for backward compatibility)
  // @deprecated Use getAnalytics() instead
  // ========================================================================

  /**
   * @deprecated Use getAnalytics() instead - this returns loan-specific data structure
   * Get complete dashboard data in one request (backward compatible)
   */
  async getDashboardData(dateRange?: DateRange, _productType?: string): Promise<DashboardData> {
    const params = new URLSearchParams()
    if (dateRange) params.append("date_range", dateRange)
    // Note: productType is ignored in new API, using use_case_id instead
    params.append("use_case_id", "forms-capital-loan")

    const response = await this.request<AnalyticsResponse>(
      `/analytics/dashboard${params ? `?${params}` : ""}`,
      { method: "GET" },
      true
    )

    // Transform universal response to legacy format for backward compatibility
    return this.transformAnalyticsToDashboardData(response)
  }

  /**
   * Transform AnalyticsResponse to legacy DashboardData format
   * @internal
   */
  private transformAnalyticsToDashboardData(response: AnalyticsResponse): DashboardData {
    return {
      overview: {
        total_applications: response.overview.total_documents || 0,
        average_risk_score: response.overview.average_risk_score || 0,
        average_monthly_income: response.overview.average_monthly_income || 0,
        eligibility_rate: response.overview.eligibility_rate || 0,
        trend: {
          applications_change_percent: response.overview.applications_change_percent || 0,
          applications_direction: response.overview.applications_direction || "neutral"
        }
      },
      demographics: {
        age_distribution: (response.dimensions.age_distribution as RangeDistributionItem[])?.map(item => ({
          range: item.label,
          count: item.count,
          percentage: item.percentage || 0
        })) || [],
        employment_breakdown: response.dimensions.employment_status as Record<string, number> || {},
        gender_breakdown: response.dimensions.gender as Record<string, number> || {},
        income_distribution: (response.dimensions.income_distribution as RangeDistributionItem[])?.map(item => ({
          range: item.label,
          min_value: item.min || 0,
          max_value: item.max || 0,
          count: item.count
        })) || [],
        risk_distribution: response.dimensions.risk_level as Record<string, number> || {}
      },
      products: {
        form_type_breakdown: response.dimensions.form_type as Record<string, number> || {},
        product_eligibility: {
          extra_cash: (response.products.extra_cash as ProductEligibilityInfo) || { eligible: 0, total: 0, percentage: 0 },
          extra_balance: (response.products.extra_balance as ProductEligibilityInfo) || { eligible: 0, total: 0, percentage: 0 },
          credit_card: (response.products.credit_card as ProductEligibilityInfo) || { eligible: 0, total: 0, percentage: 0 }
        }
      },
      monthly_trends: response.trends.map(trend => ({
        month: trend.period,
        count: trend.count,
        average_risk_score: trend.average_risk_score
      })),
      generated_at: response.metadata.generated_at
    }
  }

  // ========================================================================
  // Pre-Loan Integration Endpoints (V2 API)
  // ========================================================================

  /**
   * Store pre-loan qualification data for a document
   */
  async storePreLoanData(data: PreLoanDataRequest): Promise<{ success: boolean; message: string; document_id: string; pre_loan_status: PreLoanStatus }> {
    return this.request(
      "/integration/store",
      {
        method: "POST",
        body: JSON.stringify(data)
      },
      true
    )
  }

  /**
   * Create a new pre-loan qualification session
   */
  async createPreLoanSession(data: PreLoanSessionCreateRequest): Promise<SessionCreateResponse> {
    return this.request<SessionCreateResponse>(
      "/integration/session/create",
      {
        method: "POST",
        body: JSON.stringify(data)
      },
      true
    )
  }

  /**
   * Link a pre-loan session to a document
   */
  async linkSessionToDocument(data: DocumentLinkRequest): Promise<{ success: boolean; message: string; session_id: string; document_id: string }> {
    return this.request(
      `/integration/session/${data.session_id}/link`,
      {
        method: "POST",
        body: JSON.stringify({ document_id: data.document_id })
      },
      true
    )
  }

  /**
   * Get pre-loan session data
   */
  async getPreLoanSession(sessionId: string): Promise<SessionDataResponse> {
    return this.request<SessionDataResponse>(
      `/integration/session/${sessionId}`,
      { method: "GET" },
      true
    )
  }

  /**
   * Get pre-loan status for a document
   */
  async getPreLoanStatus(documentId: string): Promise<PreLoanStatusResponse> {
    return this.request<PreLoanStatusResponse>(
      `/integration/documents/${documentId}/pre-loan-status`,
      { method: "GET" },
      true
    )
  }

  /**
   * List all pre-qualified documents
   */
  async listPreQualifiedDocuments(limit = 50): Promise<PreLoanListResponse> {
    return this.request<PreLoanListResponse>(
      `/integration/documents/pre-qualified?limit=${limit}`,
      { method: "GET" },
      true
    )
  }

  /**
   * Get combined assessment from pre-loan and full insights
   */
  async getCombinedAssessment(documentId: string): Promise<CombinedAssessmentResponse> {
    return this.request<CombinedAssessmentResponse>(
      `/integration/documents/${documentId}/combined-assessment`,
      { method: "GET" },
      true
    )
  }

  /**
   * Get integration service status
   */
  async getIntegrationStatus(): Promise<IntegrationStatusResponse> {
    return this.request<IntegrationStatusResponse>(
      "/integration/status",
      { method: "GET" },
      true
    )
  }

  /**
   * Delete a pre-loan session
   */
  async deletePreLoanSession(sessionId: string): Promise<{ success: boolean; message: string; session_id: string }> {
    return this.request(
      `/integration/session/${sessionId}`,
      { method: "DELETE" },
      true
    )
  }

  // ========================================================================
  // Automation Endpoints (V2 API)
  // ========================================================================

  /**
   * Trigger automated approval for a single document
   */
  async triggerAutomation(data: AutomationTriggerRequest): Promise<AutomationTriggerResponse> {
    return this.request<AutomationTriggerResponse>(
      "/automation/approve",
      {
        method: "POST",
        body: JSON.stringify(data)
      },
      true
    )
  }

  /**
   * Trigger batch automation for multiple documents
   */
  async triggerBatchAutomation(data: BatchAutomationRequest): Promise<BatchAutomationResponse> {
    return this.request<BatchAutomationResponse>(
      "/automation/approve/batch",
      {
        method: "POST",
        body: JSON.stringify(data)
      },
      true
    )
  }

  /**
   * Get automation status for a document
   */
  async getAutomationStatus(documentId: string): Promise<AutomationStatusResponse> {
    return this.request<AutomationStatusResponse>(
      `/automation/documents/${documentId}/automation-status`,
      { method: "GET" },
      true
    )
  }

  /**
   * List documents eligible for automated approval
   */
  async listEligibleDocuments(limit = 50, includeProcessed = false): Promise<EligibleDocumentsResponse> {
    const params = new URLSearchParams({ limit: limit.toString(), include_processed: String(includeProcessed) })
    return this.request<EligibleDocumentsResponse>(
      `/automation/eligible?${params}`,
      { method: "GET" },
      true
    )
  }

  /**
   * Get automation configuration
   */
  async getAutomationConfig(): Promise<AutomationConfigResponse> {
    return this.request<AutomationConfigResponse>(
      "/automation/config",
      { method: "GET" },
      true
    )
  }

  /**
   * Check automation agent health
   */
  async checkAutomationHealth(): Promise<{ status: string; service: string; agent_type: string; config: AutomationConfigResponse["agent_config"] }> {
    return this.request(
      "/automation/health",
      { method: "GET" },
      true
    )
  }

  /**
   * Retry automation for a document
   */
  async retryAutomation(documentId: string): Promise<AutomationTriggerResponse> {
    return this.request<AutomationTriggerResponse>(
      `/automation/documents/${documentId}/retry`,
      { method: "POST" },
      true
    )
  }
}

// ============================================================================
// Export singleton instance
// ============================================================================

export const apiClient = new APIClient()

// Export class for custom instances
export default APIClient
