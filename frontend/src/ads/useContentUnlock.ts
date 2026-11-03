import { useQuery } from "@tanstack/react-query";
import { useCallback } from "react";

import { useAds } from "@/src/ads/AdsProvider";
import { api } from "@/src/api";
import { useAuth } from "@/src/auth";
import { queryClient } from "@/src/query-client";

/**
 * Per-USER paywall in front of lazily-AI-generated content (career descriptions, roadmap-task
 * resources, daily-plan-item resources). The underlying AI call itself is cached/shared in the
 * DB across ALL users (so the app only ever pays Anthropic once per unique piece of content),
 * but from this specific user's point of view the content should still feel freshly generated
 * for them: the very first time THEY open a given `contentId`, free users watch an ad (Premium
 * never does); every time after that, it's free — even across app restarts, since the unlock is
 * stored server-side per user, not just in memory.
 */
export function useContentUnlock(contentId: string | null | undefined, adReason: string) {
  const { user } = useAuth();
  const { watchAd } = useAds();
  const isPremium = !!user?.is_premium;

  const q = useQuery({
    queryKey: ["content-unlock", contentId],
    queryFn: () => api<{ unlocked: boolean }>(`/content/unlock-status?id=${encodeURIComponent(contentId as string)}`),
    enabled: !!contentId && !isPremium,
    staleTime: Infinity,
  });

  const unlocked = isPremium || !!q.data?.unlocked;
  const checking = !isPremium && !!contentId && q.isLoading;

  const unlock = useCallback(async () => {
    if (!contentId || unlocked) return true;
    if (!(await watchAd(adReason))) return false;
    queryClient.setQueryData(["content-unlock", contentId], { unlocked: true });
    try {
      await api("/content/unlock", { method: "POST", body: { id: contentId } });
    } catch {
      // Non-fatal: worst case the server forgets this unlock and they watch one more ad later.
    }
    return true;
  }, [contentId, unlocked, watchAd, adReason]);

  return { unlocked, checking, unlock };
}
