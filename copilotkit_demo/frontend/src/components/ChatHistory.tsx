"use client";

import React, { useState, useEffect, useCallback } from "react";

export interface ChatThread {
  id: string;
  name: string;
  createdAt: number;
}

const STORAGE_KEY = "fabric-chat-threads";

function loadThreads(): ChatThread[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function saveThreads(threads: ChatThread[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(threads));
}

function newThread(): ChatThread {
  return {
    id: crypto.randomUUID(),
    name: "New Chat",
    createdAt: Date.now(),
  };
}

export function useChatHistory() {
  const [threads, setThreads] = useState<ChatThread[]>([]);
  const [activeThreadId, setActiveThreadId] = useState<string>("");

  useEffect(() => {
    const existing = loadThreads();
    if (existing.length > 0) {
      setThreads(existing);
      setActiveThreadId(existing[0].id);
    } else {
      const first = newThread();
      setThreads([first]);
      setActiveThreadId(first.id);
      saveThreads([first]);
    }
  }, []);

  const createThread = useCallback(() => {
    const thread = newThread();
    setThreads((prev) => {
      const next = [thread, ...prev];
      saveThreads(next);
      return next;
    });
    setActiveThreadId(thread.id);
  }, []);

  const selectThread = useCallback((id: string) => {
    setActiveThreadId(id);
  }, []);

  const deleteThread = useCallback(
    (id: string) => {
      setThreads((prev) => {
        const next = prev.filter((t) => t.id !== id);
        if (next.length === 0) {
          const fresh = newThread();
          saveThreads([fresh]);
          setActiveThreadId(fresh.id);
          return [fresh];
        }
        saveThreads(next);
        if (id === activeThreadId) {
          setActiveThreadId(next[0].id);
        }
        return next;
      });
    },
    [activeThreadId]
  );

  const renameThread = useCallback(
    (id: string, name: string) => {
      setThreads((prev) => {
        const next = prev.map((t) =>
          t.id === id ? { ...t, name } : t
        );
        saveThreads(next);
        return next;
      });
    },
    []
  );

  return { threads, activeThreadId, createThread, selectThread, deleteThread, renameThread };
}

export function ChatSidebar({
  threads,
  activeThreadId,
  onSelectThread,
  onNewThread,
  onDelete,
  isOpen,
  onToggle,
}: {
  threads: ChatThread[];
  activeThreadId: string;
  onSelectThread: (id: string) => void;
  onNewThread: () => void;
  onDelete: (id: string) => void;
  isOpen: boolean;
  onToggle: () => void;
}) {
  const [hoveredId, setHoveredId] = useState<string | null>(null);

  const iconBtnStyle: React.CSSProperties = {
    background: "none",
    border: "none",
    padding: 8,
    cursor: "pointer",
    color: "#01332b",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 8,
    transition: "background 0.12s",
  };

  // Collapsed: hidden completely
  if (!isOpen) {
    return null;
  }

  // Expanded: full sidebar
  return (
    <div
      style={{
        width: 280,
        minWidth: 280,
        height: "100%",
        display: "flex",
        flexDirection: "column",
        background: "#f8fafa",
        borderRight: "1px solid #e0ebe9",
        fontFamily:
          'ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
      }}
    >
      {/* Top bar: Logo (doubles as collapse) + spacer */}
      <div
        style={{
          padding: "12px 8px 4px 8px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <button
          onClick={onToggle}
          title="Close sidebar"
          style={iconBtnStyle}
          onMouseEnter={(e) => (e.currentTarget.style.background = "#e0ebe9")}
          onMouseLeave={(e) => (e.currentTarget.style.background = "none")}
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/solventumlogo.svg" alt="Solventum" style={{ height: 22, width: 22, objectFit: "contain" }} />
        </button>
      </div>

      {/* New Chat button */}
      <div style={{ padding: "4px 10px 8px" }}>
        <button
          onClick={onNewThread}
          style={{
            width: "100%",
            display: "flex",
            alignItems: "center",
            gap: 10,
            background: "none",
            color: "#01332b",
            border: "none",
            borderRadius: 8,
            padding: "10px 12px",
            fontSize: 14,
            fontWeight: 500,
            cursor: "pointer",
            transition: "background 0.12s",
          }}
          onMouseEnter={(e) => (e.currentTarget.style.background = "#e0ebe9")}
          onMouseLeave={(e) => (e.currentTarget.style.background = "none")}
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 20h9" />
            <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" />
          </svg>
          New Chat
        </button>
      </div>

      {/* Thread list */}
      <div style={{ flex: 1, overflowY: "auto", padding: "4px 10px 16px" }}>
        <div
          style={{
            fontSize: 11,
            fontWeight: 600,
            color: "#6b8a85",
            textTransform: "uppercase",
            letterSpacing: "0.08em",
            padding: "8px 8px 6px",
          }}
        >
          Recent
        </div>
        {threads.map((t) => {
          const isActive = t.id === activeThreadId;
          return (
            <div
              key={t.id}
              style={{
                padding: "10px 12px",
                marginBottom: 2,
                borderRadius: 8,
                cursor: "default",
                backgroundColor: isActive ? "#0a7b6b" : "transparent",
                color: isActive ? "#fff" : "#01332b",
                fontSize: 13,
                fontWeight: isActive ? 500 : 400,
                display: "flex",
                alignItems: "center",
                gap: 8,
              }}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0, opacity: 0.7 }}>
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
              </svg>
              <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", flex: 1, lineHeight: 1.4 }}>
                {t.name}
              </span>
            </div>
          );
        })}
      </div>

      {/* Footer */}
      <div style={{ padding: "12px 16px", borderTop: "1px solid #e0ebe9", fontSize: 11, color: "#6b8a85", textAlign: "center" }}>
        Fabric Data Agents
      </div>
    </div>
  );
}
