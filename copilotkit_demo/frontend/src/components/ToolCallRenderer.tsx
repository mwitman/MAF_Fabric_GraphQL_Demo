"use client";

import React, { useState } from "react";

// Map MCP tool name fragments to friendly labels
function friendlyToolName(name: string): { label: string; icon: string } {
  const lower = name.toLowerCase();
  if (lower.includes("sales") || lower.includes("order"))
    return { label: "Sales Agent", icon: "📊" };
  if (lower.includes("customer") || lower.includes("address"))
    return { label: "Customer Agent", icon: "👥" };
  if (lower.includes("product") || lower.includes("category"))
    return { label: "Product Agent", icon: "📦" };
  // MCP tools have hashed names — try to detect from args
  return { label: "Fabric Data Agent", icon: "🔗" };
}

function detectAgentFromArgs(args: Record<string, unknown>): { label: string; icon: string } {
  const str = JSON.stringify(args).toLowerCase();
  if (str.includes("sale") || str.includes("order"))
    return { label: "Sales Agent", icon: "📊" };
  if (str.includes("customer") || str.includes("address"))
    return { label: "Customer Agent", icon: "👥" };
  if (str.includes("product") || str.includes("category") || str.includes("model"))
    return { label: "Product Agent", icon: "📦" };
  return { label: "Fabric Data Agent", icon: "🔗" };
}

interface ToolCallRendererProps {
  name: string;
  parameters?: Record<string, unknown>;
  status: "inProgress" | "executing" | "complete";
  result?: string;
}

export function ToolCallRenderer({
  name,
  parameters,
  status,
  result,
}: ToolCallRendererProps) {
  const [expanded, setExpanded] = useState(false);

  // Try name first, fall back to inspecting args
  let tool = friendlyToolName(name);
  if (tool.label === "Fabric Data Agent" && parameters) {
    tool = detectAgentFromArgs(parameters);
  }

  const isComplete = status === "complete";
  const isRunning = status === "inProgress" || status === "executing";

  // Extract query from args for display
  const query =
    (parameters as any)?.query ||
    (parameters as any)?.input ||
    (parameters as any)?.question ||
    null;

  return (
    <div
      style={{
        margin: "8px 0",
        borderRadius: 10,
        border: "1px solid #e0ebe9",
        overflow: "hidden",
        fontFamily:
          'ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
        fontSize: 13,
      }}
    >
      {/* Header */}
      <div
        onClick={() => isComplete && setExpanded((v) => !v)}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          padding: "10px 14px",
          backgroundColor: isComplete ? "#f0f7f6" : "#fafcfb",
          cursor: isComplete ? "pointer" : "default",
          transition: "background 0.12s",
        }}
      >
        {/* Status indicator */}
        <span style={{ fontSize: 16 }}>
          {isRunning ? (
            <span
              style={{
                display: "inline-block",
                width: 16,
                height: 16,
                border: "2px solid #0a7b6b",
                borderTopColor: "transparent",
                borderRadius: "50%",
                animation: "spin 0.8s linear infinite",
              }}
            />
          ) : (
            <span style={{ color: "#0a7b6b" }}>✓</span>
          )}
        </span>

        {/* Icon + Label */}
        <span>{tool.icon}</span>
        <span style={{ fontWeight: 500, color: "#01332b" }}>
          {isRunning ? `Querying ${tool.label}...` : `Queried ${tool.label}`}
        </span>

        {/* Query preview */}
        {query && (
          <span
            style={{
              color: "#6b8a85",
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
              flex: 1,
              marginLeft: 4,
            }}
          >
            — {String(query)}
          </span>
        )}

        {/* Expand arrow */}
        {isComplete && (
          <span
            style={{
              color: "#6b8a85",
              fontSize: 12,
              transform: expanded ? "rotate(180deg)" : "rotate(0deg)",
              transition: "transform 0.15s",
              marginLeft: "auto",
            }}
          >
            ▼
          </span>
        )}
      </div>

      {/* Expanded details */}
      {expanded && isComplete && (
        <div
          style={{
            padding: "10px 14px",
            borderTop: "1px solid #e0ebe9",
            backgroundColor: "#fff",
          }}
        >
          {parameters && Object.keys(parameters).length > 0 && (
            <div style={{ marginBottom: 8 }}>
              <div
                style={{
                  fontSize: 11,
                  fontWeight: 600,
                  color: "#6b8a85",
                  textTransform: "uppercase",
                  letterSpacing: "0.05em",
                  marginBottom: 4,
                }}
              >
                Parameters
              </div>
              <pre
                style={{
                  backgroundColor: "#f8fafa",
                  padding: 8,
                  borderRadius: 6,
                  fontSize: 12,
                  overflow: "auto",
                  maxHeight: 150,
                  margin: 0,
                  color: "#01332b",
                }}
              >
                {JSON.stringify(parameters, null, 2)}
              </pre>
            </div>
          )}
          {result && (
            <div>
              <div
                style={{
                  fontSize: 11,
                  fontWeight: 600,
                  color: "#6b8a85",
                  textTransform: "uppercase",
                  letterSpacing: "0.05em",
                  marginBottom: 4,
                }}
              >
                Result
              </div>
              <pre
                style={{
                  backgroundColor: "#f8fafa",
                  padding: 8,
                  borderRadius: 6,
                  fontSize: 12,
                  overflow: "auto",
                  maxHeight: 200,
                  margin: 0,
                  color: "#01332b",
                  whiteSpace: "pre-wrap",
                  wordBreak: "break-word",
                }}
              >
                {result}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
