"use client"

import { useState } from "react"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Package, Truck, CheckCircle, Clock, ChevronRight, Search, Download } from "lucide-react"

export default function ShipmentManagement() {
  const [searchTerm, setSearchTerm] = useState("")
  const [filterStatus, setFilterStatus] = useState<"all" | "pending" | "in-transit" | "delivered">("all")
  const [expandedId, setExpandedId] = useState<string | null>(null)

  const mockShipments = [
    {
      id: "SHIP-2024-001",
      documents: ["INV-2024-001", "PO-2024-12345"],
      origin: "Warehouse A, Chicago, IL",
      destination: "Customer Site, New York, NY",
      status: "in-transit",
      estimatedDelivery: "2024-01-18",
      actualDelivery: null,
      items: 42,
      weight: "1,250 lbs",
      carrier: "FedEx",
      trackingNumber: "FDX123456789",
      stages: [
        { name: "Picked", completed: true, date: "2024-01-15" },
        { name: "Packed", completed: true, date: "2024-01-15" },
        { name: "Shipped", completed: true, date: "2024-01-16" },
        { name: "In Transit", completed: true, date: "2024-01-16" },
        { name: "Delivery", completed: false, date: null },
      ],
    },
    {
      id: "SHIP-2024-002",
      documents: ["RCP-001", "MNF-Jan-2024"],
      origin: "Warehouse B, Los Angeles, CA",
      destination: "Distribution Center, Denver, CO",
      status: "delivered",
      estimatedDelivery: "2024-01-17",
      actualDelivery: "2024-01-17",
      items: 128,
      weight: "3,450 lbs",
      carrier: "UPS",
      trackingNumber: "UPS987654321",
      stages: [
        { name: "Picked", completed: true, date: "2024-01-14" },
        { name: "Packed", completed: true, date: "2024-01-14" },
        { name: "Shipped", completed: true, date: "2024-01-14" },
        { name: "In Transit", completed: true, date: "2024-01-15" },
        { name: "Delivery", completed: true, date: "2024-01-17" },
      ],
    },
    {
      id: "SHIP-2024-003",
      documents: ["INV-2024-002"],
      origin: "Warehouse A, Chicago, IL",
      destination: "Customer Site, Miami, FL",
      status: "pending",
      estimatedDelivery: "2024-01-20",
      actualDelivery: null,
      items: 56,
      weight: "1,890 lbs",
      carrier: "DHL",
      trackingNumber: "DHL456789123",
      stages: [
        { name: "Picked", completed: false, date: null },
        { name: "Packed", completed: false, date: null },
        { name: "Shipped", completed: false, date: null },
        { name: "In Transit", completed: false, date: null },
        { name: "Delivery", completed: false, date: null },
      ],
    },
  ]

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "delivered":
        return <CheckCircle className="w-5 h-5 text-green-600" />
      case "in-transit":
        return <Truck className="w-5 h-5 text-primary" />
      case "pending":
        return <Clock className="w-5 h-5 text-amber-600" />
      default:
        return null
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case "delivered":
        return "bg-green-100 text-green-700"
      case "in-transit":
        return "bg-primary/10 text-primary"
      case "pending":
        return "bg-amber-100 text-amber-700"
      default:
        return "bg-gray-100 text-gray-700"
    }
  }

  const filteredShipments = mockShipments.filter((shipment) => {
    const matchesSearch =
      shipment.id.toLowerCase().includes(searchTerm.toLowerCase()) ||
      shipment.trackingNumber.toLowerCase().includes(searchTerm.toLowerCase())
    const matchesFilter = filterStatus === "all" || shipment.status === filterStatus
    return matchesSearch && matchesFilter
  })

  const progress = (shipment: any) => {
    const completed = shipment.stages.filter((s: any) => s.completed).length
    return (completed / shipment.stages.length) * 100
  }

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="mb-8">
        <h1 className="text-4xl font-bold text-foreground mb-2">Shipment Management</h1>
        <p className="text-muted-foreground">Track and manage your document shipments in real-time.</p>
      </div>

      {/* Status Summary */}
      <div className="grid grid-cols-4 gap-4 mb-8">
        <Card className="p-4">
          <p className="text-sm text-muted-foreground mb-1">Total Shipments</p>
          <p className="text-2xl font-bold text-foreground">{mockShipments.length}</p>
        </Card>
        <Card className="p-4">
          <p className="text-sm text-muted-foreground mb-1">Pending</p>
          <p className="text-2xl font-bold text-amber-600">
            {mockShipments.filter((s) => s.status === "pending").length}
          </p>
        </Card>
        <Card className="p-4">
          <p className="text-sm text-muted-foreground mb-1">In Transit</p>
          <p className="text-2xl font-bold text-primary">
            {mockShipments.filter((s) => s.status === "in-transit").length}
          </p>
        </Card>
        <Card className="p-4">
          <p className="text-sm text-muted-foreground mb-1">Delivered</p>
          <p className="text-2xl font-bold text-green-600">
            {mockShipments.filter((s) => s.status === "delivered").length}
          </p>
        </Card>
      </div>

      {/* Search and Filters */}
      <div className="flex gap-4 mb-6">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
          <Input
            type="text"
            placeholder="Search by shipment ID or tracking number..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="pl-10"
          />
        </div>
        <div className="flex gap-2">
          {["all", "pending", "in-transit", "delivered"].map((status) => (
            <button
              key={status}
              onClick={() => setFilterStatus(status as any)}
              className={`px-4 py-2 rounded-lg font-medium transition-colors capitalize ${
                filterStatus === status
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted text-foreground hover:bg-border"
              }`}
            >
              {status}
            </button>
          ))}
        </div>
        <Button variant="outline" className="flex items-center gap-2 bg-transparent">
          <Download className="w-4 h-4" />
          Export
        </Button>
      </div>

      {/* Shipments List */}
      <div className="space-y-4">
        {filteredShipments.map((shipment) => (
          <Card key={shipment.id} className="overflow-hidden hover:shadow-lg transition-shadow">
            {/* Shipment Header */}
            <button
              onClick={() => setExpandedId(expandedId === shipment.id ? null : shipment.id)}
              className="w-full p-6 flex items-center gap-4 hover:bg-muted/30 transition-colors text-left"
            >
              {getStatusIcon(shipment.status)}
              <div className="flex-1 min-w-0">
                <p className="font-semibold text-foreground text-lg mb-1">{shipment.id}</p>
                <p className="text-sm text-muted-foreground">
                  {shipment.origin} → {shipment.destination}
                </p>
              </div>
              <div className="text-right">
                <span
                  className={`inline-block px-3 py-1 rounded-full text-xs font-semibold ${getStatusColor(
                    shipment.status,
                  )}`}
                >
                  {shipment.status === "in-transit"
                    ? "In Transit"
                    : shipment.status.charAt(0).toUpperCase() + shipment.status.slice(1)}
                </span>
                <p className="text-sm text-muted-foreground mt-2">Est. {shipment.estimatedDelivery}</p>
              </div>
              <ChevronRight
                className={`w-5 h-5 text-muted-foreground transition-transform ${
                  expandedId === shipment.id ? "transform rotate-90" : ""
                }`}
              />
            </button>

            {/* Expanded Details */}
            {expandedId === shipment.id && (
              <div className="border-t border-border px-6 py-6 bg-muted/30">
                {/* Key Information */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
                  <div>
                    <p className="text-sm text-muted-foreground mb-1">Tracking Number</p>
                    <p className="font-semibold text-foreground">{shipment.trackingNumber}</p>
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground mb-1">Carrier</p>
                    <p className="font-semibold text-foreground">{shipment.carrier}</p>
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground mb-1">Items</p>
                    <p className="font-semibold text-foreground">{shipment.items} units</p>
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground mb-1">Weight</p>
                    <p className="font-semibold text-foreground">{shipment.weight}</p>
                  </div>
                </div>

                {/* Progress Bar */}
                <div className="mb-8">
                  <div className="flex justify-between items-center mb-3">
                    <h4 className="font-semibold text-foreground">Shipment Progress</h4>
                    <span className="text-sm text-muted-foreground">{Math.round(progress(shipment))}%</span>
                  </div>
                  <div className="w-full bg-border rounded-full h-2">
                    <div
                      className="bg-primary h-2 rounded-full transition-all"
                      style={{ width: `${progress(shipment)}%` }}
                    ></div>
                  </div>
                </div>

                {/* Stages Timeline */}
                <div className="mb-8">
                  <h4 className="font-semibold text-foreground mb-4">Shipment Stages</h4>
                  <div className="space-y-3">
                    {shipment.stages.map((stage: any, idx: number) => (
                      <div key={idx} className="flex items-start gap-4">
                        <div className="flex flex-col items-center">
                          <div
                            className={`w-8 h-8 rounded-full flex items-center justify-center font-semibold text-sm ${
                              stage.completed ? "bg-green-600 text-white" : "bg-border text-muted-foreground"
                            }`}
                          >
                            {stage.completed ? "✓" : idx + 1}
                          </div>
                          {idx < shipment.stages.length - 1 && (
                            <div className={`w-0.5 h-12 ${stage.completed ? "bg-green-600" : "bg-border"}`}></div>
                          )}
                        </div>
                        <div className="pt-1">
                          <p className="font-medium text-foreground">{stage.name}</p>
                          {stage.date && <p className="text-sm text-muted-foreground">{stage.date}</p>}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Associated Documents */}
                <div className="mb-8">
                  <h4 className="font-semibold text-foreground mb-3">Associated Documents</h4>
                  <div className="space-y-2">
                    {shipment.documents.map((doc, i) => (
                      <div
                        key={i}
                        className="flex items-center gap-2 p-3 bg-card rounded-lg border border-border hover:border-primary transition-colors cursor-pointer"
                      >
                        <Package className="w-4 h-4 text-muted-foreground" />
                        <span className="text-foreground font-medium">{doc}</span>
                        <ChevronRight className="w-4 h-4 text-muted-foreground ml-auto" />
                      </div>
                    ))}
                  </div>
                </div>

                {/* Action Buttons */}
                <div className="flex gap-3">
                  <Button variant="outline">Print Label</Button>
                  <Button variant="outline">Download Docs</Button>
                  {shipment.status !== "delivered" && (
                    <Button className="bg-primary hover:bg-primary/90">Update Status</Button>
                  )}
                </div>
              </div>
            )}
          </Card>
        ))}
      </div>

      {filteredShipments.length === 0 && (
        <Card className="p-12 text-center">
          <Truck className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
          <h3 className="text-lg font-semibold text-foreground mb-2">No shipments found</h3>
          <p className="text-muted-foreground">Try adjusting your search or filter criteria</p>
        </Card>
      )}
    </div>
  )
}
