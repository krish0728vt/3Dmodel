import { describe, expect, it } from "vitest";

import { aiStatusLabel, providerStateLabel, systemInfoRows } from "./SystemInfo";
import type { AIProviderStatus, VersionResponse } from "../types/api";

const version: VersionResponse = {
  app_version: "0.19.0",
  schema_version: "1",
  build: "4e90c94",
  python_version: "3.11.9",
  cad_engine: "CadQuery 2.8.0",
  ai_configured: true,
  ai_provider: "ollama",
  ai_provider_label: "Local AI / Ollama",
  ai_model: "qwen2.5-coder:7b",
  ai_status: "ready"
};

const ollamaReady: AIProviderStatus = {
  provider: "ollama",
  label: "Local AI / Ollama",
  state: "ready",
  ready: true,
  model: "qwen2.5-coder:7b",
  endpoint: "http://127.0.0.1:11434",
  configured: true,
  message: "Ready",
  available_models: ["qwen2.5-coder:7b"],
  nonlocal_endpoint_warning: false
};

function rowValue(rows: ReturnType<typeof systemInfoRows>, label: string): string | undefined {
  return rows.find((row) => row.label === label)?.value;
}

describe("aiStatusLabel", () => {
  it("reports configured when a key is present", () => {
    expect(aiStatusLabel(version)).toBe("CONFIGURED");
  });

  it("uses the same wording as the launcher when unconfigured", () => {
    expect(aiStatusLabel({ ...version, ai_configured: false })).toBe("AI NOT CONFIGURED");
  });

  it("reports unknown when the backend could not be reached", () => {
    expect(aiStatusLabel(null)).toBe("unknown");
  });
});

describe("systemInfoRows", () => {
  it("surfaces the version, build, and CAD engine", () => {
    const rows = systemInfoRows(version, true, "production");
    expect(rowValue(rows, "Version")).toBe("0.19.0");
    expect(rowValue(rows, "Build")).toBe("4e90c94");
    expect(rowValue(rows, "CAD engine")).toBe("CadQuery 2.8.0");
    expect(rowValue(rows, "Schema")).toBe("1");
    expect(rowValue(rows, "Python")).toBe("3.11.9");
    expect(rowValue(rows, "Frontend build")).toBe("production");
  });

  it("reports the backend as online when it is reachable", () => {
    expect(rowValue(systemInfoRows(version, true, "production"), "Backend")).toBe("ONLINE");
  });

  it("reports the backend as offline when it is not", () => {
    const rows = systemInfoRows(null, false, "production");
    expect(rowValue(rows, "Backend")).toBe("OFFLINE");
    expect(rowValue(rows, "API")).toBe("unreachable");
  });

  it("degrades every field gracefully when the version is unavailable", () => {
    const rows = systemInfoRows(null, false, "development");
    expect(rowValue(rows, "Version")).toBe("unknown");
    expect(rowValue(rows, "CAD engine")).toBe("unknown");
    expect(rowValue(rows, "Schema")).toBe("unknown");
    expect(rowValue(rows, "Python")).toBe("unknown");
    // The frontend build is known locally even with the backend down.
    expect(rowValue(rows, "Frontend build")).toBe("development");
  });

  it("says the build is unavailable rather than showing null", () => {
    const rows = systemInfoRows({ ...version, build: null }, true, "production");
    expect(rowValue(rows, "Build")).toBe("not available");
  });

  it("surfaces the AI status as its own row", () => {
    const configured = systemInfoRows(version, true, "production", ollamaReady);
    expect(rowValue(configured, "AI provider")).toBe("Local AI / Ollama");
    expect(rowValue(configured, "AI model")).toBe("qwen2.5-coder:7b");
    expect(rowValue(configured, "AI status")).toBe("READY");

    const unconfigured = systemInfoRows({ ...version, ai_configured: false }, true, "production");
    expect(rowValue(unconfigured, "AI status")).toBe("AI NOT CONFIGURED");
  });

  it("summarizes provider-specific unavailable states", () => {
    expect(providerStateLabel({ ...ollamaReady, ready: false, state: "server_unavailable" })).toBe("OLLAMA NOT RUNNING");
    expect(providerStateLabel({ ...ollamaReady, ready: false, state: "model_unavailable" })).toBe("MODEL NOT AVAILABLE");
  });

  it("never renders an undefined or null value", () => {
    for (const rows of [
      systemInfoRows(version, true, "production"),
      systemInfoRows(null, false, "production"),
      systemInfoRows({ ...version, build: null }, true, "production")
    ]) {
      for (const row of rows) {
        expect(typeof row.value).toBe("string");
        expect(row.value.length).toBeGreaterThan(0);
      }
    }
  });

  it("exposes a stable set of labels", () => {
    const labels = systemInfoRows(version, true, "production").map((row) => row.label);
    expect(labels).toEqual([
      "Version",
      "Build",
      "Backend",
      "API",
      "CAD engine",
      "Schema",
      "Python",
      "Frontend build",
      "AI provider",
      "AI model",
      "AI status"
    ]);
  });
});
