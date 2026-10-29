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
export type Roadmap = { status: "none" | "pending" | "ready" | "error"; career?: Career; milestones?: Milestone[] };

export type Resource = { type: string; platform?: string; title: string; description: string; url: string };
export type TaskResources = {
  overview: string;
  steps: string[];
  free_tips: string[];
  specializations: string[];
  time_estimate: string;
  resources: Resource[];
};
