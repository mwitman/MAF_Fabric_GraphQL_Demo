import {
  CopilotRuntime,
  ExperimentalEmptyAdapter,
  copilotRuntimeNextJSAppRouterEndpoint,
} from "@copilotkit/runtime";
import { HttpAgent } from "@ag-ui/client";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8888";

const fabricAgent = new HttpAgent({
  url: `${BACKEND_URL}/fabric_orchestrator`,
});

const runtime = new CopilotRuntime({
  agents: {
    fabric_orchestrator: fabricAgent,
  },
});

export const POST = copilotRuntimeNextJSAppRouterEndpoint({
  runtime,
  endpoint: "/api/copilotkit",
  serviceAdapter: new ExperimentalEmptyAdapter(),
}).handleRequest;
