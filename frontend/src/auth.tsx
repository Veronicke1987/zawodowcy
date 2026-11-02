import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { api, TOKEN_KEY } from "@/src/api";
import { countryToLang, getStrings, Lang, Strings } from "@/src/i18n";
import { LOCAL_COUNTRY_KEY } from "@/src/countries";
import { LOCAL_LANGUAGE_KEY } from "@/src/languages";
import { queryClient } from "@/src/query-client";
import { storage } from "@/src/utils/storage";

export type Streak = { count: number; best: number; last_counted: string; last_seen: string; pending_restore: boolean; lost_count: number };
export type User = {
  id: string;
  email: string;
  name: string;
  role: string;
  has_profile: boolean;
  is_premium: boolean;
  streak?: Streak;
  country?: string;
  ui_language?: Lang;
  roadmap_generations_used?: number;
  roadmap_generations_limit?: number;
};

type AuthCtx = {
  user: User | null;
  loading: boolean;
  lang: Lang;
  t: Strings;
  login: (email: string, password: string) => Promise<void>;
  register: (name: string, email: string, password: string, country?: string, ui_language?: string) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
  completeAuth: (res: { access_token: string; user: User }) => Promise<void>;
  setLocalCountry: (country: string) => void;
  setLocalLanguage: (language: Lang) => void;
};

const Ctx = createContext<AuthCtx>(null as unknown as AuthCtx);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [localCountry, setLocalCountry] = useState<string | null>(null);
  const [localLanguage, setLocalLanguageState] = useState<Lang | null>(null);

  useEffect(() => {
    storage.getItem<string | null>(LOCAL_COUNTRY_KEY, null).then(setLocalCountry);
    storage.getItem<Lang | null>(LOCAL_LANGUAGE_KEY, null).then(setLocalLanguageState);
  }, []);

  const setLocalLanguage = useCallback((language: Lang) => {
    storage.setItem(LOCAL_LANGUAGE_KEY, language);
    setLocalLanguageState(language);
  }, []);

  // Interface language is fully INDEPENDENT of the job-search country: the logged-in account's
  // own explicit choice once logged in (the backend always resolves this to a concrete value,
  // see public_user()/effective_language() in server.py), otherwise whatever was picked locally
  // before registering, otherwise a sensible default derived from the locally-picked country.
  const lang = useMemo(
    () => user?.ui_language || localLanguage || countryToLang(localCountry),
    [user?.ui_language, localLanguage, localCountry],
  );
  const t = useMemo(() => getStrings(lang), [lang]);

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
  const register = async (name: string, email: string, password: string, country?: string, ui_language?: string) => {
    await handleAuth(await api("/auth/register", { method: "POST", body: { name, email, password, country, ui_language } }));
  };
  const logout = async () => {
    await storage.secureRemove(TOKEN_KEY);
    queryClient.clear();
    setUser(null);
  };

  return (
    <Ctx.Provider value={{ user, loading, lang, t, login, register, logout, refresh, completeAuth: handleAuth, setLocalCountry, setLocalLanguage }}>{children}</Ctx.Provider>
  );
}

export const useAuth = () => useContext(Ctx);
