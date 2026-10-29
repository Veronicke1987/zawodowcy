import React, { createContext, useCallback, useContext, useEffect, useState } from "react";

import { api, TOKEN_KEY } from "@/src/api";
import { queryClient } from "@/src/query-client";
import { storage } from "@/src/utils/storage";

export type User = { id: string; email: string; name: string; role: string; has_profile: boolean };

type AuthCtx = {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (name: string, email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
};

const Ctx = createContext<AuthCtx>(null as unknown as AuthCtx);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    const token = await storage.secureGet(TOKEN_KEY, null);
    if (!token) {
      setUser(null);
      return;
    }
    try {
      setUser(await api<User>("/auth/me"));
    } catch (e: any) {
      if (e?.status === 401) await storage.secureRemove(TOKEN_KEY);
      setUser(null);
    }
  }, []);

  useEffect(() => {
    refresh().finally(() => setLoading(false));
  }, [refresh]);

  const handleAuth = async (res: { access_token: string; user: User }) => {
    await storage.secureSet(TOKEN_KEY, res.access_token);
    queryClient.clear();
    setUser(res.user);
  };

  const login = async (email: string, password: string) => {
    await handleAuth(await api("/auth/login", { method: "POST", body: { email, password } }));
  };
  const register = async (name: string, email: string, password: string) => {
    await handleAuth(await api("/auth/register", { method: "POST", body: { name, email, password } }));
  };
  const logout = async () => {
    await storage.secureRemove(TOKEN_KEY);
    queryClient.clear();
    setUser(null);
  };

  return <Ctx.Provider value={{ user, loading, login, register, logout, refresh }}>{children}</Ctx.Provider>;
}

export const useAuth = () => useContext(Ctx);
