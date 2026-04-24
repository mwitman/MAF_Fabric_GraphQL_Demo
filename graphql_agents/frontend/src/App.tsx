import React, { useState, useCallback } from "react";
import Sidebar from "./components/Sidebar";
import ChatPanel from "./components/ChatPanel";

export interface Conversation {
  id: string;
  name: string;
  createdAt: number;
}

export default function App() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(true);

  const createConversation = useCallback(() => {
    const conv: Conversation = {
      id: crypto.randomUUID(),
      name: "New Chat",
      createdAt: Date.now(),
    };
    setConversations((prev) => [conv, ...prev]);
    setActiveId(conv.id);
  }, []);

  const deleteConversation = useCallback(
    (id: string) => {
      setConversations((prev) => prev.filter((c) => c.id !== id));
      if (activeId === id) {
        setActiveId(null);
      }
      // Fire-and-forget backend cleanup
      fetch(`/api/chat/${id}`, { method: "DELETE" }).catch(() => {});
    },
    [activeId]
  );

  const renameConversation = useCallback((id: string, name: string) => {
    setConversations((prev) =>
      prev.map((c) => (c.id === id ? { ...c, name } : c))
    );
  }, []);

  const toggleDarkMode = useCallback(() => {
    const html = document.documentElement;
    html.classList.toggle("dark");
    localStorage.setItem(
      "theme",
      html.classList.contains("dark") ? "dark" : "light"
    );
  }, []);

  const logout = useCallback(() => {
    // No-op without auth
  }, []);

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Sidebar */}
      <Sidebar
        conversations={conversations}
        activeId={activeId}
        open={sidebarOpen}
        onToggle={() => setSidebarOpen((o) => !o)}
        onCreate={createConversation}
        onSelect={setActiveId}
        onDelete={deleteConversation}
        onRename={renameConversation}
        onToggleDark={toggleDarkMode}
      />

      {/* Main area */}
      <main className="flex-1 flex flex-col min-w-0">
        {activeId ? (
          <ChatPanel
            key={activeId}
            conversationId={activeId}
            onRename={(name) => renameConversation(activeId, name)}
            onToggleSidebar={() => setSidebarOpen((o) => !o)}
            sidebarOpen={sidebarOpen}

          />
        ) : (
          <EmptyState onCreate={createConversation} />
        )}
      </main>
    </div>
  );
}

function EmptyState({ onCreate }: { onCreate: () => void }) {
  return (
    <div className="flex-1 flex items-center justify-center">
      <div className="text-center space-y-4">
        <div className="text-5xl">💬</div>
        <h1 className="text-2xl font-semibold">Fabric GraphQL Agents</h1>
        <p className="text-gray-500 dark:text-gray-400 max-w-md">
          Ask questions about sales, customers, and products from your
          Adventure Works data through natural language.
        </p>
        <button
          onClick={onCreate}
          className="px-6 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors font-medium"
        >
          Start a new chat
        </button>
      </div>
    </div>
  );
}
