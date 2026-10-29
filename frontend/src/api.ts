import { storage } from "@/src/utils/storage";

const BASE = `${process.env.EXPO_PUBLIC_BACKEND_URL}/api`;
export const TOKEN_KEY = "auth_token";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

export async function api<T = any>(path: string, init: { method?: string; body?: unknown } = {}): Promise<T> {
  const token = await storage.secureGet(TOKEN_KEY, null);
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, {
      method: init.method ?? "GET",
      headers,
      body: init.body !== undefined ? JSON.stringify(init.body) : undefined,
    });
  } catch {
    throw new ApiError("Brak połączenia z internetem. Sprawdź sieć i spróbuj ponownie.", 0);
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = typeof data?.detail === "string" ? data.detail : "Coś poszło nie tak. Spróbuj ponownie.";
    throw new ApiError(detail, res.status);
  }
  return data as T;
}

// Server-Sent-Events streaming (expo/fetch supports response.body streaming on native and web).
export async function streamChat(
  text: string,
  onDelta: (t: string) => void,
): Promise<{ remaining: number | null; error?: string }> {
  const { fetch: expoFetch } = await import("expo/fetch");
  const token = await storage.secureGet(TOKEN_KEY, null);
  let res: Awaited<ReturnType<typeof expoFetch>>;
  try {
    res = await expoFetch(`${BASE}/chat/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}`, Accept: "text/event-stream" },
      body: JSON.stringify({ text }),
    });
  } catch {
    throw new ApiError("Brak połączenia z internetem. Sprawdź sieć i spróbuj ponownie.", 0);
  }
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new ApiError(typeof data?.detail === "string" ? data.detail : "Coś poszło nie tak.", res.status);
  }
  const reader = res.body!.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  let result: { remaining: number | null; error?: string } = { remaining: null };
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    const parts = buf.split("\n\n");
    buf = parts.pop() || "";
    for (const p of parts) {
      const line = p.trim();
      if (!line.startsWith("data:")) continue;
      const ev = JSON.parse(line.slice(5).trim());
      if (ev.t) onDelta(ev.t);
      if (ev.error) result.error = ev.error;
      if (ev.done) result = { ...result, remaining: ev.remaining ?? null };
    }
  }
  return result;
}

export type PathSummary = { path_id: string; title: string; status: string; active: boolean; progress: number };
export type PathsResponse = { paths: PathSummary[]; limit: number; is_premium: boolean };

export type StudyPlan = {
  status: "none" | "pending" | "ready" | "error";
  path_id?: string;
  career?: Career;
  plan?: {
    hours_per_week: number;
    summary: string;
    weeks: { week: number; focus: string; goal: string; items: { title: string; description: string; hours: number }[] }[];
    tips: string[];
  };
};

export type Career = {
  id: string;
  title: string;
  industry?: string;
  summary: string;
  why?: string;
  match: number;
  salary?: string;
  demand?: string;
  ai_risk?: string;
  missing_skills?: string[];
  category: "now" | "future";
};

export type Recommendations = {
  status: "none" | "pending" | "ready" | "error";
  summary?: string;
  now?: Career[];
  future?: Career[];
};

export type Task = { id: string; title: string; description: string; type: string; done: boolean };
export type Milestone = {
  id: string;
  title: string;
  description: string;
  salary?: string;
  years?: string;
  requirements?: string[];
  tasks: Task[];
};
export type Roadmap = { status: "none" | "pending" | "ready" | "error"; path_id?: string; career?: Career; milestones?: Milestone[] };

export type Resource = { type: string; platform?: string; title: string; description: string; url: string };
export type TaskResources = {
  overview: string;
  steps: string[];
  free_tips: string[];
  specializations: string[];
  time_estimate: string;
  resources: Resource[];
};
