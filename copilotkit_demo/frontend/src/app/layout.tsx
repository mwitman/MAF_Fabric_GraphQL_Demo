import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "MedSurg Stitch - Fabric Data Agent Orchestration Demo",
  description:
    "Multi-agent orchestrator for Fabric Data Agents powered by CopilotKit + AG-UI",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="h-screen w-screen overflow-hidden">
      <body className="h-screen w-screen overflow-hidden">{children}</body>
    </html>
  );
}
