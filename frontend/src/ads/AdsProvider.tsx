import { useRouter } from "expo-router";
import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { AppState, Modal, Pressable, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { adsAvailable, initAds, showInterstitial, showRewarded } from "@/src/ads/ads";
import { useAuth } from "@/src/auth";
import { Button, Ionicons, Txt } from "@/src/components/ui";
import { fonts, makeStyles, radius, spacing, useTheme } from "@/src/theme";

const INTERVAL_MS = 5 * 60 * 1000;
// Only used for the web/Expo Go stand-in ad; real AdMob ads show for as long as Google decides.
const SIM_SECONDS = 3;
// How long the "thank you" screen stays up before auto-closing for the (non-actionable) interstitial.
const INTERSTITIAL_THANKS_MS = 1800;
const INTERSTITIAL_INTRO_MS = 1800;

type AdsCtx = {
  showAds: boolean;
  // Shows a rewarded ad (free users). Resolves true when the action may proceed.
  watchAd: (reason: string, count?: number) => Promise<boolean>;
  // Same, but specifically for generating a brand-new career path: Premium users skip the
  // ad UNLESS they've already used their monthly quota of free path generations, in which
  // case they also see rewarded ads to continue. Building a path always costs 2 ads.
  watchRoadmapAd: (reason: string) => Promise<boolean>;
};

const Ctx = createContext<AdsCtx>({ showAds: false, watchAd: async () => true, watchRoadmapAd: async () => true });
export const useAds = () => useContext(Ctx);

const ROADMAP_AD_COUNT = 2;

type Stage = "intro" | "playing" | "thanks";
type Sim = {
  kind: "rewarded" | "interstitial";
  reason?: string;
  stage: Stage;
  resolve: (ok: boolean) => void;
  premiumQuota?: boolean;
  index: number;
  total: number;
};

export function AdsProvider({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  const showAds = !!user && !user.is_premium;
  const [sim, setSim] = useState<Sim | null>(null);
  const lastAdAt = useRef(Date.now());
  const busy = useRef(false);
  const playingRef = useRef(false);

  useEffect(() => {
    if (!showAds) return;
    lastAdAt.current = Date.now(); // count 5 minutes from login, not from app start
    initAds().catch(() => {});
    // time spent in the background does not count toward the next ad
    let bgAt = 0;
    const sub = AppState.addEventListener("change", (s) => {
      if (s === "background") bgAt = Date.now();
      else if (s === "active" && bgAt) {
        lastAdAt.current += Date.now() - bgAt;
        bgAt = 0;
      }
    });
    return () => sub.remove();
  }, [showAds]);

  // Drives the actual ad once the user (or the auto-advancing interstitial intro)
  // moves a session into the "playing" stage. Re-runs for each ad when total > 1.
  useEffect(() => {
    if (!sim || sim.stage !== "playing" || playingRef.current) return;
    playingRef.current = true;
    const kind = sim.kind;
    const resolve = sim.resolve;
    (async () => {
      let ok: boolean;
      if (adsAvailable) {
        ok = kind === "rewarded" ? await showRewarded() : await showInterstitial().then(() => true).catch(() => false);
      } else {
        await new Promise((r) => setTimeout(r, SIM_SECONDS * 1000));
        ok = true; // the stand-in ad always "completes" successfully
      }
      playingRef.current = false;
      if (!ok) {
        setSim(null);
        resolve(false);
        return;
      }
      lastAdAt.current = Date.now();
      setSim((prev) => (prev && prev.stage === "playing" ? { ...prev, stage: "thanks" } : prev));
    })();
  }, [sim]);

  const watchAd = useCallback(
    (reason: string, count = 1) => {
      if (!showAds) return Promise.resolve(true);
      return new Promise<boolean>((resolve) => {
        busy.current = true;
        setSim({
          kind: "rewarded",
          reason,
          stage: "intro",
          index: 1,
          total: count,
          resolve: (ok) => {
            busy.current = false;
            resolve(ok);
          },
        });
      });
    },
    [showAds],
  );

  // Premium users get PREMIUM_MONTHLY_GENERATIONS new career-path generations/month ad-free
  // (tracked server-side); past that, they also need to watch ads to continue.
  // Building any career path (free, or over-quota Premium) always costs ROADMAP_AD_COUNT ads.
  const quotaExceeded = !!user?.is_premium && (user.roadmap_generations_used ?? 0) >= (user.roadmap_generations_limit ?? Infinity);
  const watchRoadmapAd = useCallback(
    (reason: string) => {
      if (!user?.is_premium) return watchAd(reason, ROADMAP_AD_COUNT);
      if (!quotaExceeded) return Promise.resolve(true);
      return new Promise<boolean>((resolve) => {
        busy.current = true;
        setSim({
          kind: "rewarded",
          reason,
          premiumQuota: true,
          stage: "intro",
          index: 1,
          total: ROADMAP_AD_COUNT,
          resolve: (ok) => {
            busy.current = false;
            resolve(ok);
          },
        });
      });
    },
    [user?.is_premium, quotaExceeded, watchAd],
  );

  // Interstitial roughly every 5 minutes of active use, never on top of another ad.
  useEffect(() => {
    if (!showAds) return;
    const t = setInterval(() => {
      if (busy.current || AppState.currentState !== "active") return;
      if (Date.now() - lastAdAt.current < INTERVAL_MS) return;
      busy.current = true;
      setSim({
        kind: "interstitial",
        stage: "intro",
        index: 1,
        total: 1,
        resolve: () => {
          busy.current = false;
        },
      });
    }, 15000);
    return () => clearInterval(t);
  }, [showAds]);

  const router = useRouter();

  const close = (ok: boolean) => {
    sim?.resolve(ok);
    setSim(null);
  };

  // Moves from the "thanks" screen of ad N straight into the "intro" of ad N+1,
  // used whenever a flow requires watching more than one ad in a row.
  const onNextAd = () => setSim((prev) => (prev ? { ...prev, stage: "intro", index: prev.index + 1 } : prev));

  return (
    <Ctx.Provider value={{ showAds, watchAd, watchRoadmapAd }}>
      {children}
      <AdModal
        sim={sim}
        onWatch={() => setSim((prev) => (prev ? { ...prev, stage: "playing" } : prev))}
        onNextAd={onNextAd}
        onPremium={() => {
          close(false);
          router.push("/premium");
        }}
        onCancel={() => close(false)}
        onThanksDone={() => close(true)}
      />
    </Ctx.Provider>
  );
}

// Custom ad shell used for both platforms: a short intro (choose to watch or go
// Premium), the ad itself (real AdMob on native, a stand-in countdown on web/Expo
// Go), and a thank-you screen that reminds users ads keep the app free.
function AdModal({
  sim,
  onWatch,
  onNextAd,
  onPremium,
  onCancel,
  onThanksDone,
}: {
  sim: Sim | null;
  onWatch: () => void;
  onNextAd: () => void;
  onPremium: () => void;
  onCancel: () => void;
  onThanksDone: () => void;
}) {
  const styles = useStyles();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const [left, setLeft] = useState(SIM_SECONDS);
  // keep the last session's content while the modal fades out
  const [view, setView] = useState<Sim | null>(sim);

  useEffect(() => {
    if (sim) setView(sim);
  }, [sim]);

  // Simulated countdown while the stand-in ad "plays" (web / Expo Go only).
  useEffect(() => {
    if (!sim || sim.stage !== "playing" || adsAvailable) return;
    setLeft(SIM_SECONDS);
    const t = setInterval(() => setLeft((x) => (x > 0 ? x - 1 : 0)), 1000);
    return () => clearInterval(t);
  }, [sim]);

  // The interstitial intro has no action to confirm — it auto-advances.
  useEffect(() => {
    if (!sim || sim.stage !== "intro" || sim.kind !== "interstitial") return;
    const t = setTimeout(onWatch, INTERSTITIAL_INTRO_MS);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sim]);

  // The interstitial "thanks" screen has no reward to claim — it auto-closes.
  useEffect(() => {
    if (!sim || sim.stage !== "thanks" || sim.kind !== "interstitial") return;
    const t = setTimeout(onThanksDone, INTERSTITIAL_THANKS_MS);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sim]);

  if (!view) return null;
  const rewarded = view.kind === "rewarded";
  const moreAdsLeft = rewarded && view.total > 1 && view.index < view.total;

  return (
    <Modal visible={!!sim} animationType="fade" statusBarTranslucent onRequestClose={() => rewarded && view.stage === "intro" && onCancel()}>
      <View style={[styles.root, { paddingTop: insets.top + spacing.lg, paddingBottom: insets.bottom + spacing.lg }]} testID="ad-modal">
        <View style={styles.top}>
          <Text style={styles.adLabel} testID="ad-counter-label">
            {view.total > 1 ? `REKLAMA ${view.index}/${view.total}` : "REKLAMA"}
          </Text>
          {view.stage === "intro" && rewarded ? (
            <Pressable testID="ad-intro-close-button" onPress={onCancel} style={styles.close} hitSlop={10}>
              <Ionicons name="close" size={22} color={colors.onSurface} />
            </Pressable>
          ) : view.stage === "playing" && !adsAvailable ? (
            <Text style={styles.counter} testID="ad-countdown">
              {left > 0 ? `Reklama trwa jeszcze ${left} s` : "Reklama kończy się…"}
            </Text>
          ) : null}
        </View>

        {view.stage === "intro" ? (
          <View style={styles.center}>
            <Ionicons name={rewarded ? "gift" : "megaphone"} size={56} color={colors.brandPrimary} />
            <Txt variant="title" style={{ textAlign: "center" }}>
              {rewarded
                ? view.premiumQuota
                  ? "Wykorzystano limit ścieżek w tym miesiącu"
                  : view.index > 1
                    ? "Obejrzyj drugą reklamę, aby odebrać nagrodę"
                    : "Obejrzyj reklamę, aby odebrać nagrodę"
                : "Za chwilę krótka reklama"}
            </Txt>
            <Txt style={{ textAlign: "center" }} testID="ad-intro-text">
              {rewarded
                ? view.premiumQuota
                  ? `Masz już Premium, ale wykorzystano w tym miesiącu limit nowych ścieżek kariery. Obejrzyj ${view.total > 1 ? `${view.total} krótkie reklamy` : "krótką reklamę"}, aby ${view.reason ?? "kontynuować"} — limit odnowi się w przyszłym miesiącu.`
                  : view.total > 1
                    ? view.index > 1
                      ? `Jeszcze jedna reklama i gotowe — zaraz ${view.reason ?? "kontynuujesz"}.`
                      : `Aby ${view.reason ?? "kontynuować i zobaczyć wyniki"}, obejrzyj ${view.total} krótkie reklamy pod rząd lub przejdź na Premium.`
                    : `Aby ${view.reason ?? "kontynuować i zobaczyć wyniki"}, obejrzyj krótką reklamę lub przejdź na Premium.`
                : "Reklamy pomagają utrzymać aplikację za darmo. Z Premium nie zobaczysz żadnych reklam."}
            </Txt>
          </View>
        ) : view.stage === "playing" ? (
          <View style={styles.center}>
            <Ionicons name="megaphone" size={56} color={colors.brandPrimary} />
            <Txt variant="title" style={{ textAlign: "center" }}>
              Tu pojawi się reklama
            </Txt>
            {!adsAvailable ? (
              <Text style={styles.note}>W podglądzie to symulacja — prawdziwe reklamy Google pojawią się w zbudowanej aplikacji.</Text>
            ) : (
              <Txt style={{ textAlign: "center" }}>Ładowanie reklamy…</Txt>
            )}
          </View>
        ) : (
          <View style={styles.center}>
            <View style={styles.thanksIcon}>
              <Ionicons name="heart" size={32} color={colors.onBrandPrimary} />
            </View>
            <Txt variant="title" style={{ textAlign: "center" }} testID="ad-thanks-title">
              {moreAdsLeft ? "Dziękujemy! Jeszcze jedna reklama" : "Dziękujemy za obejrzenie reklamy!"}
            </Txt>
            <Txt style={{ textAlign: "center" }}>
              {moreAdsLeft
                ? "Obejrzyj drugą reklamę, aby dokończyć i odebrać nagrodę."
                : `${rewarded ? "Twoja nagroda czeka — " : ""}Dzięki reklamom aplikacja Zawodowcy jest darmowa dla wszystkich.`}
            </Txt>
          </View>
        )}

        <View style={{ gap: spacing.sm }}>
          {view.stage === "intro" ? (
            <>
              {rewarded ? <Button testID="ad-intro-watch-button" title="Obejrzyj reklamę" icon="play" onPress={onWatch} /> : null}
              {!view.premiumQuota && view.index === 1 ? (
                <Button testID="ad-go-premium" title="Przejdź na Premium" variant={rewarded ? "ghost" : "primary"} icon="diamond" onPress={onPremium} />
              ) : null}
            </>
          ) : view.stage === "thanks" && rewarded ? (
            moreAdsLeft ? (
              <Button testID="ad-thanks-next-button" title="Obejrzyj kolejną reklamę" icon="play" onPress={onNextAd} />
            ) : (
              <Button testID="ad-thanks-continue-button" title="Super, kontynuuj" icon="checkmark" onPress={onThanksDone} />
            )
          ) : null}
        </View>
      </View>
    </Modal>
  );
}

const useStyles = makeStyles((c) => ({
  root: { flex: 1, backgroundColor: c.surface, paddingHorizontal: spacing.xl, justifyContent: "space-between" },
  top: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", minHeight: 44 },
  adLabel: { fontFamily: fonts.bold, fontSize: 11, letterSpacing: 1, color: c.muted, backgroundColor: c.surfaceSecondary, paddingHorizontal: 8, paddingVertical: 4, borderRadius: radius.sm },
  counter: { fontFamily: fonts.semibold, fontSize: 13, color: c.muted },
  close: { width: 44, height: 44, borderRadius: 22, backgroundColor: c.surfaceSecondary, alignItems: "center", justifyContent: "center" },
  center: { alignItems: "center", gap: spacing.md, paddingHorizontal: spacing.md },
  note: { fontFamily: fonts.medium, fontSize: 12, color: c.muted, textAlign: "center", marginTop: spacing.md },
  thanksIcon: { width: 64, height: 64, borderRadius: 32, backgroundColor: c.brandPrimary, alignItems: "center", justifyContent: "center" },
}));
