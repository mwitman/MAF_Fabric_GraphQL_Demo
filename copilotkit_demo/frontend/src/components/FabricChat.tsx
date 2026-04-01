"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  CopilotChat,
  useConfigureSuggestions,
  useRenderTool,
} from "@copilotkit/react-core/v2";
import { type ChatThread, ChatSidebar } from "./ChatHistory";
import { ToolCallRenderer } from "./ToolCallRenderer";

interface ChatHistoryState {
  threads: ChatThread[];
  activeThreadId: string;
  createThread: () => void;
  selectThread: (id: string) => void;
  deleteThread: (id: string) => void;
  renameThread: (id: string, name: string) => void;
}

function useIsMobile(breakpoint = 768) {
  const [isMobile, setIsMobile] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia(`(max-width: ${breakpoint}px)`);
    setIsMobile(mq.matches);
    const handler = (e: MediaQueryListEvent) => setIsMobile(e.matches);
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, [breakpoint]);
  return isMobile;
}

export function FabricChat({ chatHistory }: { chatHistory: ChatHistoryState }) {
  const { threads, activeThreadId, createThread, selectThread, deleteThread, renameThread } =
    chatHistory;
  const isMobile = useIsMobile();
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const namedThreadsRef = React.useRef<Set<string>>(new Set());

  // Auto-collapse sidebar on mobile
  useEffect(() => {
    if (isMobile) setSidebarOpen(false);
  }, [isMobile]);

  // Auto-name thread from first user message
  useEffect(() => {
    if (!activeThreadId) return;
    // Skip if we already named this thread
    if (namedThreadsRef.current.has(activeThreadId)) return;
    // Skip if it already has a real name (not "New Chat")
    const thread = threads.find((t) => t.id === activeThreadId);
    if (thread && thread.name !== "New Chat") {
      namedThreadsRef.current.add(activeThreadId);
      return;
    }

    const observer = new MutationObserver(() => {
      const userMsgs = document.querySelectorAll('[data-testid="copilot-user-message"]');
      if (userMsgs.length > 0) {
        const text = userMsgs[0].textContent?.trim();
        if (text) {
          const name = text.length > 40 ? text.slice(0, 40) + "..." : text;
          renameThread(activeThreadId, name);
          namedThreadsRef.current.add(activeThreadId);
          observer.disconnect();
        }
      }
    });

    observer.observe(document.body, { childList: true, subtree: true });
    return () => observer.disconnect();
  }, [activeThreadId, renameThread]);

  useConfigureSuggestions({
    suggestions: [
      {
        title: "Top customers by order count",
        message: "Who are the top 5 customers by total number of orders?",
      },
      {
        title: "Product categories",
        message: "List all product categories and how many products are in each.",
      },
      {
        title: "Recent orders",
        message: "Show me the 10 most recent orders with customer name, total, and status.",
      },
      {
        title: "Customer addresses",
        message: "What shipping addresses are on file for customer 'Adventure Works'?",
      },
    ],
    available: "always",
  });

  // Stable wildcard tool renderer
  const renderFn = useCallback(
    (props: any) => <ToolCallRenderer {...props} />,
    [],
  );
  useRenderTool({ name: "*", render: renderFn }, []);

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        display: "flex",
        flexDirection: "row",
      }}
    >
      {/* Sidebar */}
      <ChatSidebar
        threads={threads}
        activeThreadId={activeThreadId}
        onSelectThread={selectThread}
        onNewThread={createThread}
        onDelete={deleteThread}
        isOpen={sidebarOpen}
        onToggle={() => setSidebarOpen((v) => !v)}
      />

      {/* Main chat area */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column" }}>
        {/* Header bar — hidden on mobile when sidebar is closed (logo button replaces it) */}
        {(sidebarOpen || !isMobile) && (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              padding: "0 20px",
              height: 52,
              borderBottom: "1px solid #e8e8e8",
              backgroundColor: "#fff",
              fontFamily:
                'ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
            }}
          >
            {/* Sidebar toggle — show when sidebar is closed */}
            {!sidebarOpen && (
              <button
                onClick={() => setSidebarOpen(true)}
                style={{
                  background: "none",
                  border: "none",
                  padding: 6,
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  borderRadius: 6,
                  marginRight: 8,
                }}
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src="/solventumlogo.svg" alt="Open sidebar" style={{ height: 22, width: 22, objectFit: "contain" }} />
              </button>
            )}
            <span style={{ fontWeight: 600, color: "#01332b", fontSize: 15, letterSpacing: "-0.01em" }}>
              MedSurg Stitch
            </span>
          </div>
        )}

        {/* Mobile: floating Solventum logo to open sidebar */}
        {isMobile && !sidebarOpen && (
          <button
            onClick={() => setSidebarOpen(true)}
            style={{
              position: "absolute",
              top: 12,
              left: 12,
              zIndex: 10,
              background: "#fff",
              border: "1px solid #e0ebe9",
              borderRadius: 10,
              padding: 8,
              cursor: "pointer",
              boxShadow: "0 2px 8px rgba(0,0,0,0.08)",
              display: "flex",
              alignItems: "center",
            }}
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="/solventumlogo.svg" alt="Open menu" style={{ height: 22, width: 22, objectFit: "contain" }} />
          </button>
        )}

        {/* Chat */}
        <div style={{ flex: 1, overflow: "hidden" }}>
          <CopilotChat
            className="h-full max-w-5xl mx-auto"
          />
        </div>
      </div>
    </div>
  );
}
