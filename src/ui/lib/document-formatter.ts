/**
 * Universal Document Formatter
 *
 * Dynamically formats extracted document fields for display,
 * intelligently detecting structure and organizing content.
 * Works with ANY document type - no hardcoding.
 */

export interface FieldValue {
    value: any
    bbox?: {
        left: number
        top: number
        width: number
        height: number
        page: number
    }
    block_type?: string
    confidence?: string
}

export interface FormattedField {
    key: string
    displayName: string
    value: any
    isEmpty: boolean
    isNumeric: boolean
    isDate: boolean
    isAmount: boolean
    category?: string
}

/**
 * Format a field key into a human-readable display name
 * Dynamically handles any naming convention
 */
export function formatFieldName(key: string): string {
    if (!key) return ''

    // Remove leading numbers and underscores (e.g., "1_regime" -> "regime")
    let formatted = key.replace(/^\d+_*/, '')

    // Split on underscores and special chars
    formatted = formatted
        .replace(/_/g, ' ')
        .replace(/([a-z])([A-Z])/g, '$1 $2') // camelCase to spaces
        .trim()

    // Capitalize each word
    formatted = formatted
        .split(' ')
        .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
        .join(' ')

    return formatted || key
}

/**
 * Check if a value is empty/null
 */
export function isEmptyValue(value: any): boolean {
    if (value === null || value === undefined || value === '') return true

    const strValue = String(value).trim().toLowerCase()
    return (
        strValue === '<empty>' ||
        strValue === 'null' ||
        strValue === 'undefined' ||
        strValue === 'n/a' ||
        strValue === 'none'
    )
}

/**
 * Extract actual value from field data
 */
export function extractValue(fieldData: any): any {
    if (typeof fieldData === 'object' && fieldData !== null && 'value' in fieldData) {
        return fieldData.value
    }
    return fieldData
}

/**
 * Detect if value is numeric (amount, weight, quantity, etc.)
 */
export function isNumericField(key: string, value: any): boolean {
    if (typeof value === 'number') return true

    const numericKeywords = ['amount', 'total', 'price', 'cost', 'value', 'weight', 'quantity', 'qty', 'mass', 'rate', 'fob', 'freight', 'insurance', 'ncy', 'fcy']
    const keyLower = key.toLowerCase()

    if (numericKeywords.some(kw => keyLower.includes(kw))) {
        return true
    }

    // Check if value looks numeric (has numbers and possibly commas/periods)
    if (typeof value === 'string') {
        return /^[\d,.\s]+$/.test(value.trim())
    }

    return false
}

/**
 * Detect if value is a date
 */
export function isDateField(key: string, value: any): boolean {
    const dateKeywords = ['date', 'datetime', 'time', 'day', 'month', 'year']
    const keyLower = key.toLowerCase()

    if (dateKeywords.some(kw => keyLower.includes(kw))) {
        return true
    }

    // Check if value looks like a date
    if (typeof value === 'string') {
        return /\d{1,4}[-/]\d{1,2}[-/]\d{1,4}/.test(value)
    }

    return false
}

/**
 * Detect if value is a monetary amount
 */
export function isAmountField(key: string): boolean {
    const amountKeywords = ['amount', 'total', 'price', 'cost', 'value', 'fob', 'freight', 'insurance', 'ncy', 'fcy', 'invoice']
    const keyLower = key.toLowerCase()
    return amountKeywords.some(kw => keyLower.includes(kw))
}

/**
 * Auto-categorize field based on key patterns
 * Returns a category name or undefined
 */
export function categorizeField(key: string): string | undefined {
    const keyLower = key.toLowerCase()

    // Financial keywords
    if (/amount|total|price|cost|value|fob|freight|insurance|ncy|fcy|invoice|payment|bank/.test(keyLower)) {
        return 'Financial'
    }

    // Party/entity keywords
    if (/consignee|exporter|importer|shipper|buyer|seller|vendor|customer|party|declarant|representative/.test(keyLower)) {
        return 'Parties'
    }

    // Shipment/transport keywords
    if (/ship|vessel|transport|container|port|loading|delivery|freight|carrier/.test(keyLower)) {
        return 'Shipment & Transport'
    }

    // Goods/product keywords
    if (/goods|product|item|commodity|description|quantity|weight|mass|unit|marks|package/.test(keyLower)) {
        return 'Goods & Products'
    }

    // Document info keywords
    if (/number|no|id|reference|ref|code|regime|date|office/.test(keyLower)) {
        return 'Document Information'
    }

    return undefined
}

/**
 * Format all fields from a document response
 */
export function formatDocumentFields(fields: Record<string, any>): FormattedField[] {
    return Object.entries(fields)
        .filter(([key]) => !key.startsWith('_')) // Skip internal fields
        .map(([key, fieldData]) => {
            const value = extractValue(fieldData)

            return {
                key,
                displayName: formatFieldName(key),
                value,
                isEmpty: isEmptyValue(value),
                isNumeric: isNumericField(key, value),
                isDate: isDateField(key, value),
                isAmount: isAmountField(key),
                category: categorizeField(key),
            }
        })
}

/**
 * Group formatted fields by category
 */
export function groupFieldsByCategory(fields: FormattedField[]): Map<string, FormattedField[]> {
    const grouped = new Map<string, FormattedField[]>()

    fields.forEach(field => {
        const category = field.category || 'Other'
        if (!grouped.has(category)) {
            grouped.set(category, [])
        }
        grouped.get(category)!.push(field)
    })

    return grouped
}

/**
 * Sort fields by spatial position (document order)
 * Uses bounding box coordinates to maintain original layout
 */
export function sortFieldsSpatially(fields: FormattedField[], fieldsData: Record<string, any>): FormattedField[] {
    return fields.sort((a, b) => {
        // Get bbox data
        const aData = fieldsData[a.key]
        const bData = fieldsData[b.key]

        const aBbox = (typeof aData === 'object' && aData?.bbox) ? aData.bbox : null
        const bBbox = (typeof bData === 'object' && bData?.bbox) ? bData.bbox : null

        // If neither has bbox, sort alphabetically
        if (!aBbox && !bBbox) {
            return a.key.localeCompare(b.key)
        }

        // Fields without bbox go to end
        if (!aBbox) return 1
        if (!bBbox) return -1

        // Sort by page first
        if (aBbox.page !== bBbox.page) {
            return aBbox.page - bBbox.page
        }

        // Then by vertical position (top)
        const topDiff = aBbox.top - bBbox.top
        if (Math.abs(topDiff) > 0.05) { // 5% threshold for "same row"
            return topDiff
        }

        // If on same row, sort by horizontal position (left)
        return aBbox.left - bBbox.left
    })
}

/**
 * Sort fields intelligently based on importance and type (fallback if no bbox)
 */
export function sortFields(fields: FormattedField[]): FormattedField[] {
    return fields.sort((a, b) => {
        // Empty fields go last
        if (a.isEmpty !== b.isEmpty) {
            return a.isEmpty ? 1 : -1
        }

        // Prioritize document numbers/IDs
        const aIsId = /number|no|id|reference|ref/.test(a.key.toLowerCase())
        const bIsId = /number|no|id|reference|ref/.test(b.key.toLowerCase())
        if (aIsId !== bIsId) {
            return aIsId ? -1 : 1
        }

        // Then by category importance
        const categoryOrder = ['Document Information', 'Parties', 'Goods & Products', 'Shipment & Transport', 'Financial', 'Other']
        const aIndex = categoryOrder.indexOf(a.category || 'Other')
        const bIndex = categoryOrder.indexOf(b.category || 'Other')
        if (aIndex !== bIndex) {
            return aIndex - bIndex
        }

        // Finally alphabetically
        return a.displayName.localeCompare(b.displayName)
    })
}

/**
 * Format value for display based on field type
 */
export function formatValueForDisplay(field: FormattedField): string {
    if (field.isEmpty) {
        return '-'
    }

    const value = field.value

    // Handle objects
    if (typeof value === 'object' && value !== null) {
        return JSON.stringify(value)
    }

    // Format numbers with commas for readability
    if (field.isNumeric && typeof value === 'string') {
        // Already has formatting, return as-is
        return value
    }

    return String(value)
}
