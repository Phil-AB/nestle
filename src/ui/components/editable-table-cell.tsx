/**
 * Editable Table Cell Component
 * Provides inline editing capabilities for table cells
 */

import React, { useState } from 'react'

interface EditableCellProps {
  cellKey: string
  content: string
  isHeader?: boolean
  style?: any
  onEdit?: (cellKey: string, newValue: string) => void
  CellComponent: React.ComponentType<any>
}

export function EditableCell({ cellKey, content, isHeader = false, style, onEdit, CellComponent }: EditableCellProps) {
  const [isEditing, setIsEditing] = useState(false)
  const [editValue, setEditValue] = useState(content)

  const handleSave = () => {
    if (onEdit && editValue !== content) {
      onEdit(cellKey, editValue)
    }
    setIsEditing(false)
  }

  const handleCancel = () => {
    setEditValue(content)
    setIsEditing(false)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSave()
    } else if (e.key === 'Escape') {
      handleCancel()
    }
  }

  const handleDoubleClick = () => {
    setIsEditing(true)
  }

  return (
    <CellComponent
      colSpan={style?.colspan}
      rowSpan={style?.rowspan}
      className={`${style?.className || ''} ${!isHeader ? 'cursor-pointer hover:bg-muted/20' : ''}`}
      style={{
        backgroundColor: style?.backgroundColor ?
          (style.backgroundColor.startsWith('#') ? style.backgroundColor :
           convertNamedColor(style.backgroundColor)) : undefined,
        verticalAlign: style?.alignment === 'middle' ? 'middle' :
                      style?.alignment === 'top' ? 'top' : 'center',
        textAlign: /\d+:\d+/.test(content) && !isEditing ? 'center' : 'left'
      }}
      onDoubleClick={!isHeader ? handleDoubleClick : undefined}
      title={!isHeader ? "Double-click to edit" : undefined}
    >
      {isEditing ? (
        <input
          type="text"
          value={editValue}
          onChange={(e) => setEditValue(e.target.value)}
          onKeyDown={handleKeyDown}
          onBlur={handleSave}
          autoFocus
          className="w-full px-2 py-1 text-sm border border-primary rounded focus:outline-none focus:ring-2 focus:ring-primary bg-background"
        />
      ) : (
        <span className="block w-full">
          {content}
        </span>
      )}
    </CellComponent>
  )
}

function convertNamedColor(color: string): string {
  const colorMap: Record<string, string> = {
    'e6e6fa': '#e6e6fa',  // lavender
    'white': '#ffffff',
    'black': '#000000',
    'gray': '#808080',
    'silver': '#c0c0c0',
    'red': '#ff0000',
    'blue': '#0000ff',
    'green': '#008000',
    'yellow': '#ffff00',
    'orange': '#ffa500',
    'purple': '#800080'
  }
  return colorMap[color.toLowerCase()] || color
}