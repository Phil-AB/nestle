"use client"

import { useEffect, useState } from "react"
import { apiClient, type BankingInsightsResponse, type BankingCustomerListItem } from "@/lib/api-client"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Loader, FileText, Download, CheckCircle, XCircle, TrendingUp, AlertTriangle, RefreshCw, User, Briefcase, Shield, CreditCard } from "lucide-react"
import { toast } from "sonner"

export default function DocumentInsightsPage() {
  const [customers, setCustomers] = useState<BankingCustomerListItem[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedCustomerId, setSelectedCustomerId] = useState<string | null>(null)
  const [insights, setInsights] = useState<BankingInsightsResponse | null>(null)
  const [generating, setGenerating] = useState(false)

  useEffect(() => {
    loadCustomers()
  }, [])

  const loadCustomers = async () => {
    try {
      const customerList = await apiClient.listBankingCustomers(50)
      setCustomers(customerList)
    } catch (error) {
      toast.error("Failed to load customers")
      console.error(error)
    } finally {
      setLoading(false)
    }
  }

  const handleSelectCustomer = async (customerId: string) => {
    setSelectedCustomerId(customerId)
    setGenerating(true)
    setInsights(null)

    try {
      const customerInsights = await apiClient.generateBankingInsights(customerId, true)
      setInsights(customerInsights)
    } catch (error) {
      toast.error("Failed to generate insights")
      console.error(error)
    } finally {
      setGenerating(false)
    }
  }

  const handleDownloadPdf = async () => {
    if (insights?.pdf_path) {
      // The pdf_path is already the full API URL, just open it
      // Extract filename for download attribute
      const filename = insights.pdf_path.split('/').pop() || "insights.pdf"

      try {
        const response = await fetch(insights.pdf_path)
        if (!response.ok) {
          throw new Error(`Failed to download: ${response.statusText}`)
        }
        const blob = await response.blob()
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = filename
        document.body.appendChild(a)
        a.click()
        document.body.removeChild(a)
        URL.revokeObjectURL(url)
        toast.success("PDF downloaded successfully")
      } catch (error) {
        toast.error("Failed to download PDF")
        console.error(error)
      }
    }
  }

  const getRiskColor = (score: number) => {
    if (score >= 70) return "text-green-600"
    if (score >= 50) return "text-yellow-600"
    return "text-red-600"
  }

  const getRiskBadgeVariant = (score: number): "default" | "secondary" | "destructive" | "outline" => {
    if (score >= 70) return "default"
    if (score >= 50) return "secondary"
    return "destructive"
  }

  const getApprovalBadge = (status: string): "default" | "secondary" | "destructive" | "outline" => {
    if (status === "AUTO_APPROVE") return "default"
    if (status === "MANUAL_REVIEW") return "secondary"
    return "destructive"
  }

  return (
    <div className="p-8 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold flex items-center gap-3">
            <TrendingUp className="w-8 h-8 text-primary" />
            Document Insights
          </h1>
          <p className="text-muted-foreground mt-2">
            AI-powered document analysis with risk assessment and intelligent recommendations
          </p>
        </div>
        <Button onClick={loadCustomers} variant="outline" size="sm">
          <RefreshCw className="w-4 h-4 mr-2" />
          Refresh
        </Button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Customer List */}
        <Card className="lg:col-span-1">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <User className="w-5 h-5" />
              Documents
            </CardTitle>
            <CardDescription>Select a document to generate insights</CardDescription>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="flex items-center justify-center py-8">
                <Loader className="w-6 h-6 animate-spin text-muted-foreground" />
              </div>
            ) : customers.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                No documents found in database
              </div>
            ) : (
              <div className="space-y-2 max-h-[600px] overflow-y-auto">
                {customers.map((customer) => (
                  <div
                    key={customer.document_id}
                    onClick={() => handleSelectCustomer(customer.document_id)}
                    className={`p-4 rounded-lg border cursor-pointer transition-all hover:shadow-md ${
                      selectedCustomerId === customer.document_id
                        ? "border-primary bg-primary/5"
                        : "border-border hover:bg-muted"
                    }`}
                  >
                    <div className="font-medium">{customer.customer_name || "Unknown"}</div>
                    <div className="text-sm text-muted-foreground mt-1 flex items-center gap-3">
                      {customer.age && <span>{customer.age} yrs</span>}
                      <span>•</span>
                      <span className="capitalize">{customer.employment_status}</span>
                      <span>•</span>
                      <span>GHS {customer.estimated_income.toLocaleString()}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Insights Panel */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Shield className="w-5 h-5" />
              Document Insights
            </CardTitle>
            <CardDescription>
              {selectedCustomerId ? "AI-generated analysis and recommendations" : "Select a document to view insights"}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {!selectedCustomerId ? (
              <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
                <FileText className="w-16 h-16 mb-4 opacity-50" />
                <p>Select a customer from the list to view their banking insights</p>
              </div>
            ) : generating ? (
              <div className="flex flex-col items-center justify-center py-16">
                <Loader className="w-8 h-8 animate-spin text-primary mb-4" />
                <p className="text-muted-foreground">Generating AI insights...</p>
              </div>
            ) : insights ? (
              <div className="space-y-6">
                {/* Customer Profile */}
                <div className="space-y-4">
                  <h3 className="font-semibold text-lg">Customer Profile</h3>
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-4 text-sm">
                    <div>
                      <span className="text-muted-foreground">Name:</span>
                      <p className="font-medium">{insights.customer_profile.customer_name}</p>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Age:</span>
                      <p className="font-medium">{insights.customer_profile.age || "N/A"}</p>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Employment:</span>
                      <p className="font-medium capitalize">{insights.customer_profile.employment_status}</p>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Occupation:</span>
                      <p className="font-medium">{insights.customer_profile.occupation}</p>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Employer:</span>
                      <p className="font-medium">{insights.customer_profile.employer}</p>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Income:</span>
                      <p className="font-medium">GHS {insights.customer_profile.estimated_monthly_income.toLocaleString()}</p>
                    </div>
                  </div>
                </div>

                {/* Risk Assessment */}
                <div className="space-y-4">
                  <h3 className="font-semibold text-lg">Risk Assessment</h3>
                  <div className="flex items-center gap-6">
                    <div className="flex items-center gap-3">
                      <div className={`w-20 h-20 rounded-full flex items-center justify-center text-2xl font-bold text-white ${
                        insights.risk_assessment.risk_score >= 70
                          ? "bg-gradient-to-br from-green-500 to-green-600"
                          : insights.risk_assessment.risk_score >= 50
                          ? "bg-gradient-to-br from-yellow-500 to-yellow-600"
                          : "bg-gradient-to-br from-red-500 to-red-600"
                      }`}>
                        {insights.risk_assessment.risk_score}
                      </div>
                      <div>
                        <p className="text-sm text-muted-foreground">Risk Score</p>
                        <p className={`text-2xl font-bold ${getRiskColor(insights.risk_assessment.risk_score)}`}>
                          {insights.risk_assessment.risk_score}/100
                        </p>
                      </div>
                    </div>
                    <div className="space-y-2">
                      <Badge variant={getRiskBadgeVariant(insights.risk_assessment.risk_score)}>
                        {insights.risk_assessment.risk_level} Risk
                      </Badge>
                      <Badge variant="outline">
                        {insights.risk_assessment.creditworthiness} Creditworthiness
                      </Badge>
                    </div>
                  </div>

                  {/* Factors */}
                  <div className="space-y-2">
                    {insights.risk_assessment.factors.positive.length > 0 && (
                      <div>
                        <p className="text-sm font-medium text-green-600 mb-2">Positive Factors</p>
                        <div className="space-y-1">
                          {insights.risk_assessment.factors.positive.map((factor, i) => (
                            <div key={i} className="text-sm flex items-start gap-2 p-2 bg-green-50 rounded">
                              <CheckCircle className="w-4 h-4 text-green-600 mt-0.5 flex-shrink-0" />
                              {factor}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                    {insights.risk_assessment.factors.concerns.length > 0 && (
                      <div>
                        <p className="text-sm font-medium text-red-600 mb-2">Areas of Concern</p>
                        <div className="space-y-1">
                          {insights.risk_assessment.factors.concerns.map((factor, i) => (
                            <div key={i} className="text-sm flex items-start gap-2 p-2 bg-red-50 rounded">
                              <AlertTriangle className="w-4 h-4 text-red-600 mt-0.5 flex-shrink-0" />
                              {factor}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>

                {/* Product Eligibility */}
                <div className="space-y-4">
                  <h3 className="font-semibold text-lg flex items-center gap-2">
                    <Briefcase className="w-5 h-5" />
                    Product Eligibility
                  </h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {/* Extra Cash */}
                    <div className={`p-4 rounded-lg border-2 ${
                      insights.product_eligibility.extra_cash.eligible
                        ? "border-green-500 bg-green-50"
                        : "border-gray-200 bg-gray-50"
                    }`}>
                      <div className="flex items-center justify-between mb-2">
                        <h4 className="font-medium">Extra Cash Loan</h4>
                        {insights.product_eligibility.extra_cash.eligible ? (
                          <CheckCircle className="w-5 h-5 text-green-600" />
                        ) : (
                          <XCircle className="w-5 h-5 text-gray-400" />
                        )}
                      </div>
                      <div className="text-sm space-y-1">
                        <Badge variant={insights.product_eligibility.extra_cash.eligible ? "default" : "secondary"}>
                          {insights.product_eligibility.extra_cash.eligible ? "Eligible" : "Not Eligible"}
                        </Badge>
                        {insights.product_eligibility.extra_cash.eligible && (
                          <>
                            <p>Up to GHS {insights.product_eligibility.extra_cash.max_amount.toLocaleString()}</p>
                            <p className="text-xs text-muted-foreground">
                              Interest: {insights.product_eligibility.extra_cash.interest_rate}%
                            </p>
                          </>
                        )}
                      </div>
                    </div>

                    {/* Extra Balance */}
                    <div className={`p-4 rounded-lg border-2 ${
                      insights.product_eligibility.extra_balance.eligible
                        ? "border-green-500 bg-green-50"
                        : "border-gray-200 bg-gray-50"
                    }`}>
                      <div className="flex items-center justify-between mb-2">
                        <h4 className="font-medium">Extra Balance Overdraft</h4>
                        {insights.product_eligibility.extra_balance.eligible ? (
                          <CheckCircle className="w-5 h-5 text-green-600" />
                        ) : (
                          <XCircle className="w-5 h-5 text-gray-400" />
                        )}
                      </div>
                      <div className="text-sm space-y-1">
                        <Badge variant={insights.product_eligibility.extra_balance.eligible ? "default" : "secondary"}>
                          {insights.product_eligibility.extra_balance.eligible ? "Eligible" : "Not Eligible"}
                        </Badge>
                        {insights.product_eligibility.extra_balance.eligible && (
                          <>
                            <p>Limit: GHS {insights.product_eligibility.extra_balance.overdraft_limit.toLocaleString()}</p>
                            <p className="text-xs text-muted-foreground">
                              Monthly fee: GHS {insights.product_eligibility.extra_balance.monthly_fee}
                            </p>
                          </>
                        )}
                      </div>
                    </div>

                    {/* Credit Card */}
                    <div className={`p-4 rounded-lg border-2 ${
                      insights.product_eligibility.credit_card.eligible
                        ? "border-green-500 bg-green-50"
                        : "border-gray-200 bg-gray-50"
                    }`}>
                      <div className="flex items-center justify-between mb-2">
                        <h4 className="font-medium flex items-center gap-2">
                          <CreditCard className="w-4 h-4" />
                          Credit Card
                        </h4>
                        {insights.product_eligibility.credit_card.eligible ? (
                          <CheckCircle className="w-5 h-5 text-green-600" />
                        ) : (
                          <XCircle className="w-5 h-5 text-gray-400" />
                        )}
                      </div>
                      <div className="text-sm space-y-1">
                        <Badge variant={insights.product_eligibility.credit_card.eligible ? "default" : "secondary"}>
                          {insights.product_eligibility.credit_card.eligible ? "Eligible" : "Not Eligible"}
                        </Badge>
                        {insights.product_eligibility.credit_card.eligible && (
                          <p>Limit: GHS {insights.product_eligibility.credit_card.credit_limit.toLocaleString()}</p>
                        )}
                      </div>
                    </div>

                    {/* Premium Account */}
                    <div className={`p-4 rounded-lg border-2 ${
                      insights.product_eligibility.premium_account.eligible
                        ? "border-green-500 bg-green-50"
                        : "border-gray-200 bg-gray-50"
                    }`}>
                      <div className="flex items-center justify-between mb-2">
                        <h4 className="font-medium">Premium Account</h4>
                        {insights.product_eligibility.premium_account.eligible ? (
                          <CheckCircle className="w-5 h-5 text-green-600" />
                        ) : (
                          <XCircle className="w-5 h-5 text-gray-400" />
                        )}
                      </div>
                      <div className="text-sm space-y-1">
                        <Badge variant={insights.product_eligibility.premium_account.eligible ? "default" : "secondary"}>
                          {insights.product_eligibility.premium_account.eligible ? "Eligible" : "Not Eligible"}
                        </Badge>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Recommendations */}
                {insights.recommendations.account_upgrades.length > 0 ||
                 insights.recommendations.cross_sell_products.length > 0 ||
                 insights.recommendations.next_steps.length > 0 ? (
                  <div className="space-y-4">
                    <h3 className="font-semibold text-lg">Recommendations</h3>
                    <div className="space-y-2">
                      {insights.recommendations.account_upgrades.map((rec, i) => (
                        <div key={i} className="text-sm p-3 bg-blue-50 rounded border-l-4 border-blue-500">
                          <div className="font-medium">{rec.title}</div>
                          <div className="text-xs text-muted-foreground mt-1">{rec.description}</div>
                          {rec.priority && (
                            <Badge variant="outline" className="mt-2 text-xs capitalize">
                              {rec.priority} Priority
                            </Badge>
                          )}
                        </div>
                      ))}
                      {insights.recommendations.cross_sell_products.map((rec, i) => (
                        <div key={i} className="text-sm p-3 bg-purple-50 rounded border-l-4 border-purple-500">
                          <div className="font-medium">{rec.title}</div>
                          <div className="text-xs text-muted-foreground mt-1">{rec.description}</div>
                          {rec.priority && (
                            <Badge variant="outline" className="mt-2 text-xs capitalize">
                              {rec.priority} Priority
                            </Badge>
                          )}
                        </div>
                      ))}
                      {insights.recommendations.next_steps.map((rec, i) => (
                        <div key={i} className="text-sm p-3 bg-yellow-50 rounded border-l-4 border-yellow-500">
                          <div className="font-medium">{rec.title}</div>
                          <div className="text-xs text-muted-foreground mt-1">{rec.description}</div>
                          {rec.priority && (
                            <Badge variant="outline" className="mt-2 text-xs capitalize">
                              {rec.priority} Priority
                            </Badge>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                ) : null}

                {/* Automated Decisions */}
                <div className="space-y-4">
                  <h3 className="font-semibold text-lg">Automated Decisions</h3>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <span className="text-sm text-muted-foreground">Account Approval</span>
                      <div className="mt-1">
                        <Badge variant={getApprovalBadge(insights.automated_decisions.account_approval)}>
                          {insights.automated_decisions.account_approval}
                        </Badge>
                      </div>
                    </div>
                    <div>
                      <span className="text-sm text-muted-foreground">Credit Pre-Qualification</span>
                      <p className="mt-1 font-medium">{insights.automated_decisions.credit_pre_qualification}</p>
                    </div>
                    <div>
                      <span className="text-sm text-muted-foreground">Tier Assignment</span>
                      <p className="mt-1 font-medium">{insights.automated_decisions.tier_assignment}</p>
                    </div>
                    <div>
                      <span className="text-sm text-muted-foreground">Priority Level</span>
                      <p className="mt-1 font-medium capitalize">{insights.automated_decisions.priority_level.toLowerCase()}</p>
                    </div>
                  </div>
                </div>

                {/* Download PDF */}
                {insights.pdf_path && (
                  <div className="pt-4 border-t">
                    <Button onClick={handleDownloadPdf} className="w-full">
                      <Download className="w-4 h-4 mr-2" />
                      Download PDF Report
                    </Button>
                  </div>
                )}
              </div>
            ) : null}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
