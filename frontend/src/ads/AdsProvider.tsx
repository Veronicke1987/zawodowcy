import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { AppState, Modal, Pressable, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { adsAvailable, initAds, showInterstitial, showRewarded } from "@/src/ads/ads";
import { useAuth } from "@/src/auth";
import { Button, Ionicons, Txt } from "@/src/components/ui";
import { fonts, makeStyles, radius, spacing, useTheme } from "@/src/theme";
import { useRouter } from "expo-router";

const INTERVAL_MS = 5 * 60 * 1000;
const SIM_SECONDS = 5;

type AdsCtx = {
  showAds: boolean;
  // Shows a rewarded ad (free users). Resolves true when the action may proceed.
  watchAd: (reason: string) => Promise<boolean>;
};

const Ctx = createContext<AdsCtx>({ showAds: false, watchAd: async () => true });
export const useAds = () => useContext(Ctx);

type Sim = { kind: "rewarded" | "interstitial"; reason?: string; resolve: (ok: boolean) => void };

export function AdsProvider({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  const showAds = !!user && !user.is_premium;
  const [sim, setSim] = useState<Sim | null>(null);
  const lastAdAt = useRef(Date.now());
  const busy = useRef(false);

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

  const simulate = (kind: Sim["kind"], reason?: string) =>
    new Promise<boolean>((resolve) => setSim({ kind, reason, resolve }));

  const watchAd = useCallback(
    async (reason: string) => {
      if (!showAds) return true;
      busy.current = true;
      try {
        const ok = adsAvailable ? await showRewarded() : await simulate("rewarded", reason);
        if (ok) lastAdAt.current = Date.now();
        return ok;
      } finally {
        busy.current = false;
      }
    },
    [showAds],
  );

  // Interstitial roughly every 5 minutes of active use, never on top of another ad.
  useEffect(() => {
    if (!showAds) return;
    const t = setInterval(async () => {
      if (busy.current || AppState.currentState !== "active") return;
      if (Date.now() - lastAdAt.current < INTERVAL_MS) return;
      busy.current = true;
      try {
        if (adsAvailable) await showInterstitial();
        else await simulate("interstitial");
      } finally {
        lastAdAt.current = Date.now();
        busy.current = false;
      }
    }, 15000);
    return () => clearInterval(t);
  }, [showAds]);

  return (
    <Ctx.Provider value={{ showAds, watchAd }}>
      {children}
      <SimulatedAd
        sim={sim}
        onClose={(ok) => {
          sim?.resolve(ok);
          setSim(null);
        }}
      />
    </Ctx.Provider>
  );
}

// Stand-in ad for Expo Go and the web preview (real AdMob ads need an app build).
function SimulatedAd({ sim, onClose }: { sim: Sim | null; onClose: (ok: boolean) => void }) {
  const styles = useStyles();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const [left, setLeft] = useState(SIM_SECONDS);
  // keep the last ad's content while the modal fades out
  const [view, setView] = useState<Sim | null>(sim);

  useEffect(() => {
    if (!sim) return;
    setView(sim);
    setLeft(SIM_SECONDS);
    const t = setInterval(() => setLeft((x) => (x > 0 ? x - 1 : 0)), 1000);
    return () => clearInterval(t);
  }, [sim]);

  const rewarded = view?.kind === "rewarded";
  return (
    <Modal visible={!!sim} animationType="fade" onRequestClose={() => left === 0 && onClose(true)} statusBarTranslucent>
      <View style={[styles.root, { paddingTop: insets.top + spacing.lg, paddingBottom: insets.bottom + spacing.lg }]} testID="ad-modal">
        <View style={styles.top}>
          <Text style={styles.adLabel}>REKLAMA</Text>
          {left > 0 ? (
            <Text style={styles.counter} testID="ad-countdown">
              {rewarded ? `Nagroda za ${left} s` : `Możesz zamknąć za ${left} s`}
            </Text>
          ) : (
            <Pressable testID="ad-close-button" onPress={() => onClose(true)} style={styles.close} hitSlop={10}>
              <Ionicons name="close" size={22} color={colors.onSurface} />
            </Pressable>
          )}
        </View>
        <View style={styles.center}>
          <Ionicons name="megaphone" size={56} color={colors.brandPrimary} />
          <Txt variant="title" style={{ textAlign: "center" }}>
            Tu pojawi się reklama
          </Txt>
          <Txt style={{ textAlign: "center" }}>
            {rewarded
              ? `Obejrzyj reklamę, aby ${view?.reason ?? "kontynuować"}.`
              : "Reklamy pomagają utrzymać aplikację za darmo."}
          </Txt>
          <Text style={styles.note}>W podglądzie to symulacja — prawdziwe reklamy Google pojawią się w zbudowanej aplikacji.</Text>
        </View>
        <View style={{ gap: spacing.sm }}>
          {left === 0 && rewarded ? <Button testID="ad-continue-button" title="Kontynuuj" icon="checkmark" onPress={() => onClose(true)} /> : null}
          <Button
            testID="ad-go-premium"
            title="Wyłącz reklamy z Premium"
            variant="ghost"
            icon="diamond"
            onPress={() => {
              onClose(false);
              router.push("/premium");
            }}
          />
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
}));
