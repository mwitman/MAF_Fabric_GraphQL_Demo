"use client";

import React from "react";
import { CopilotKit } from "@copilotkit/react-core";
import "@copilotkit/react-core/v2/styles.css";
import { FabricChat } from "@/components/FabricChat";
import { useChatHistory } from "@/components/ChatHistory";

export default function Home() {
  const chatHistory = useChatHistory();

  if (!chatHistory.activeThreadId) return null;

  return (
    <CopilotKit
      key={chatHistory.activeThreadId}
      runtimeUrl="/api/copilotkit"
      showDevConsole={false}
      agent="fabric_orchestrator"
    >
      <FabricChat chatHistory={chatHistory} />
    </CopilotKit>
  );
}
