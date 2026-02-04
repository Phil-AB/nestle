"use client"

import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { ArrowRight, FileText, CheckCircle, AlertCircle, TrendingUp } from "lucide-react"
import Link from "next/link"
import { useQuery } from "@tanstack/react-query"
import { apiClient } from "@/lib/api-client"
import { formatDistanceToNow } from "date-fns"

export default function Dashboard() {
  // Fetch document statistics from API
  const {
    data: statsData,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["document-stats"],
    queryFn: () => apiClient.getDocumentStats(),
    refetchInterval: 30000, // Refetch every 30 seconds
    staleTime: 10000, // Consider data stale after 10 seconds
  })

  const stats = [
    {
      label: "Documents Processed",
      value: statsData?.data.total_documents?.toLocaleString() ?? "—",
      change: statsData ? "Total documents" : "Loading...",
      icon: FileText,
      color: "bg-blue-100 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400",
    },
    {
      label: "Extraction Success",
      value: statsData ? `${statsData.data.extraction_success}%` : "—",
      change: "Success rate",
      icon: CheckCircle,
      color: "bg-green-100 text-green-600 dark:bg-green-900/30 dark:text-green-400",
    },
    {
      label: "Documents Generated",
      value: statsData?.data.documents_generated?.toLocaleString() ?? "—",
      change: "Approved documents",
      icon: TrendingUp,
      color: "bg-purple-100 text-purple-600 dark:bg-purple-900/30 dark:text-purple-400",
    },
    {
      label: "Pending Documents",
      value: statsData?.data.pending_documents?.toLocaleString() ?? "—",
      change: "Awaiting processing",
      icon: AlertCircle,
      color: "bg-amber-100 text-amber-600 dark:bg-amber-900/30 dark:text-amber-400",
    },
  ]

  const recentActivity = statsData?.recent_activity ?? []

  return (
    <div className="p-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-4xl font-bold text-foreground mb-2">Dashboard</h1>
        <p className="text-muted-foreground">
          {error
            ? "Error loading dashboard data. Please try again later."
            : "Welcome back! Here's what's happening with your documents today."}
        </p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        {stats.map((stat) => {
          const Icon = stat.icon
          return (
            <Card key={stat.label} className="p-6 hover:shadow-lg transition-shadow">
              <div className="flex items-start justify-between mb-4">
                <div>
                  <p className="text-sm text-muted-foreground mb-1">{stat.label}</p>
                  <p className="text-3xl font-bold text-foreground">{isLoading ? "..." : stat.value}</p>
                </div>
                <div className={`p-2 rounded-lg ${stat.color}`}>
                  <Icon className="w-6 h-6" />
                </div>
              </div>
              <p className="text-sm text-muted-foreground">{stat.change}</p>
            </Card>
          )
        })}
      </div>

      {/* Quick Actions */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="p-8 lg:col-span-2">
          <h2 className="text-xl font-bold text-foreground mb-4">Recent Activity</h2>
          <div className="space-y-4">
            {isLoading ? (
              <div className="flex items-center justify-center py-8">
                <div className="text-muted-foreground">Loading activity...</div>
              </div>
            ) : recentActivity.length === 0 ? (
              <div className="flex items-center justify-center py-8">
                <div className="text-muted-foreground">No recent activity</div>
              </div>
            ) : (
              recentActivity.map((activity, i) => (
                <div key={i} className="flex items-center gap-3 py-3 border-b border-border last:border-0">
                  <div className={`w-2 h-2 rounded-full ${
                    activity.status === "complete" ? "bg-green-500" :
                    activity.status === "failed" ? "bg-red-500" :
                    activity.status === "processing" ? "bg-amber-500" :
                    "bg-primary"
                  }`}></div>
                  <span className="text-foreground flex-1">{activity.activity}</span>
                  {activity.document_name && (
                    <span className="text-sm text-muted-foreground truncate max-w-[150px]">{activity.document_name}</span>
                  )}
                  <span className="text-sm text-muted-foreground whitespace-nowrap">
                    {activity.created_at && formatDistanceToNow(new Date(activity.created_at), { addSuffix: true })}
                  </span>
                </div>
              ))
            )}
          </div>
        </Card>

        <Card className="p-8">
          <h2 className="text-xl font-bold text-foreground mb-6">Quick Actions</h2>
          <div className="space-y-3">
            <Link href="/upload">
              <Button className="w-full justify-between bg-primary hover:bg-primary/90">
                Upload Document
                <ArrowRight className="w-4 h-4" />
              </Button>
            </Link>
            <Link href="/generation">
              <Button variant="outline" className="w-full justify-between bg-transparent">
                Generate Documents
                <ArrowRight className="w-4 h-4" />
              </Button>
            </Link>
            <Link href="/insights">
              <Button variant="outline" className="w-full justify-between bg-transparent">
                View Insights
                <ArrowRight className="w-4 h-4" />
              </Button>
            </Link>
          </div>
        </Card>
      </div>
    </div>
  )
}
