/**
 * API client module for ClauseCompass REST and SSE streaming endpoints.
 */

export async function fetchHealth() {
  const res = await fetch("/api/health");
  if (!res.ok) throw new Error("Health check failed");
  return res.json();
}

export async function fetchSamples() {
  const res = await fetch("/api/samples");
  if (!res.ok) throw new Error("Failed to load sample agreements");
  return res.json();
}

export async function fetchSampleText(sampleId) {
  const res = await fetch(`/api/samples/${sampleId}`);
  if (!res.ok) throw new Error(`Failed to load sample ${sampleId}`);
  return res.json();
}

export async function analyzeDocumentWithStream(formData, onProgress) {
  const response = await fetch("/api/analyze/stream", {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(errorText || "Document analysis failed.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let finalResult = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n\n");
    buffer = lines.pop() || "";

    for (const chunk of lines) {
      const trimmed = chunk.trim();
      if (trimmed.startsWith("data: ")) {
        try {
          const payload = JSON.parse(trimmed.slice(6));
          if (payload.stage === "error") {
            throw new Error(payload.message || "Analysis error");
          }
          if (onProgress) {
            onProgress(payload);
          }
          if (payload.stage === "complete" && payload.result) {
            finalResult = payload.result;
          }
        } catch (e) {
          console.warn("SSE parse error:", e);
        }
      }
    }
  }

  if (!finalResult) {
    throw new Error("Analysis completed without result payload.");
  }
  return finalResult;
}

export async function askQuestion(payload) {
  const res = await fetch("/api/qa", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Q&A failed" }));
    throw new Error(err.detail || "Failed to answer question.");
  }
  return res.json();
}

export async function compareDocuments(payload) {
  const res = await fetch("/api/compare", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Comparison failed" }));
    throw new Error(err.detail || "Failed to compare documents.");
  }
  return res.json();
}

export async function downloadExport(endpoint, analysisData, defaultFilename) {
  const res = await fetch(`/api/export/${endpoint}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(analysisData),
  });
  if (!res.ok) throw new Error(`Export to ${endpoint} failed`);
  
  const blob = await res.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = defaultFilename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  window.URL.revokeObjectURL(url);
}
