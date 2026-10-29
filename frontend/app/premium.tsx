import { LinearGradient } from "expo-linear-gradient";
import { useRouter } from "expo-router";
import { useState } from "react";
import { Pressable, ScrollView, Text, View } from "react-native";
import Animated, { FadeInDown } from "react-native-reanimated";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api } from "@/src/api";
import { useAuth } from "@/src/auth";
import { Button, ErrorBox, IconButton, Ionicons, IconName, Txt } from "@/src/components/ui";
import { queryClient } from "@/src/query-client";
import { playSuccess } from "@/src/sound";
import { fonts, makeStyles, radius, spacing, useTheme } from "@/src/theme";

const PLANS = [
  { key: "monthly", label: "Miesięczny", price: "19,99 zł", per: "/ miesiąc", note: "Anuluj w każdej chwili" },
  { key: "yearly", label: "Roczny", price: "149,99 zł", per: "/ rok", note: "Tylko 12,50 zł miesięcznie · oszczędzasz 37%" },
] as const;

const PERKS: { icon: IconName; title: string; text: string }[] = [
  { icon: "eye-off", title: "Bez reklam", text: "Żadnych reklam przy ścieżkach, planie nauki ani w trakcie korzystania." },
  { icon: "flash", title: "Wszystko od razu", text: "Ścieżki kariery i plan nauki generujesz bez oglądania reklam." },
  { icon: "chatbubbles", title: "Więcej rozmów z doradcą", text: "Do 10 wiadomości dziennie — dwa razy więcej niż w darmowej wersji." },
];

export default function Premium() {
  const insets = useSafeAreaInsets();
  const styles = useStyles();
  const { colors } = useTheme();
  const router = useRouter();
  const { user, refresh } = useAuth();
  const [plan, setPlan] = useState<"monthly" | "yearly">("yearly");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const active = !!user?.is_premium;

  const after = async () => {
    await refresh();
    queryClient.invalidateQueries();
  };

  const subscribe = async () => {
    setLoading(true);
    setError("");
    try {
      await api("/premium/subscribe", { method: "POST", body: { plan } });
      playSuccess();
      await after();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const cancel = async () => {
    setLoading(true);
    try {
      await api("/premium/cancel", { method: "POST" });
      await after();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <View style={styles.root}>
      <ScrollView contentContainerStyle={{ paddingBottom: 140 + insets.bottom }}>
        <LinearGradient colors={[colors.brandPrimary, colors.brandSecondary]} style={[styles.hero, { paddingTop: insets.top + 64 }]}>
          <View style={styles.crown}>
            <Ionicons name="diamond" size={34} color={colors.brandPrimary} />
          </View>
          <Text style={styles.heroTitle}>Zawodowcy Premium</Text>
          <Text style={styles.heroSub}>Szybciej do nowego zawodu — z planem i doradcą na każdy dzień.</Text>
        </LinearGradient>

        <View style={styles.body}>
          {active ? (
            <View style={styles.activeBox} testID="premium-active">
              <Ionicons name="checkmark-circle" size={24} color={colors.success} />
              <View style={{ flex: 1 }}>
                <Txt variant="heading">Masz aktywne Premium</Txt>
                <Txt variant="caption">Wszystkie funkcje są odblokowane.</Txt>
              </View>
            </View>
          ) : null}

          {PERKS.map((p, i) => (
            <Animated.View key={p.title} entering={FadeInDown.delay(i * 80)} style={styles.perk}>
              <View style={styles.perkIcon}>
                <Ionicons name={p.icon} size={22} color={colors.onBrandTertiary} />
              </View>
              <View style={{ flex: 1 }}>
                <Txt variant="heading">{p.title}</Txt>
                <Txt>{p.text}</Txt>
              </View>
            </Animated.View>
          ))}

          {!active ? (
            <View style={{ gap: spacing.md, marginTop: spacing.sm }}>
              {PLANS.map((p) => {
                const sel = plan === p.key;
                return (
                  <Pressable
                    key={p.key}
                    testID={`premium-plan-${p.key}`}
                    onPress={() => setPlan(p.key)}
                    style={[styles.plan, { borderColor: sel ? colors.brandPrimary : colors.border }]}
                  >
                    <Ionicons name={sel ? "radio-button-on" : "radio-button-off"} size={22} color={sel ? colors.brandPrimary : colors.borderStrong} />
                    <View style={{ flex: 1 }}>
                      <Text style={styles.planLabel}>{p.label}</Text>
                      <Txt variant="caption">{p.note}</Txt>
                    </View>
                    <Text style={styles.price}>
                      {p.price}
                      <Text style={styles.per}> {p.per}</Text>
                    </Text>
                  </Pressable>
                );
              })}
              <View style={styles.demo}>
                <Ionicons name="information-circle-outline" size={18} color={colors.muted} />
                <Text style={styles.demoText}>Tryb demo — płatności nie są jeszcze pobierane. Premium włączy się od razu.</Text>
              </View>
            </View>
          ) : null}
          {error ? <ErrorBox testID="premium-error" message={error} /> : null}
        </View>
      </ScrollView>

      <View style={[styles.topBar, { top: insets.top + spacing.sm }]}>
        <IconButton testID="premium-close" icon="close" onPress={() => (router.canGoBack() ? router.back() : router.replace("/(tabs)"))} />
      </View>

      <View style={[styles.sticky, { paddingBottom: insets.bottom + spacing.md }]}>
        {active ? (
          <Button testID="premium-cancel-button" title="Wyłącz Premium" variant="ghost" onPress={cancel} loading={loading} />
        ) : (
          <Button testID="premium-subscribe-button" title="Aktywuj Premium" icon="diamond" onPress={subscribe} loading={loading} />
        )}
      </View>
    </View>
  );
}

const useStyles = makeStyles((c) => ({
  root: { flex: 1, backgroundColor: c.surface },
  hero: { paddingHorizontal: spacing.xl, paddingBottom: spacing.xxl, alignItems: "center", gap: spacing.sm },
  crown: { width: 72, height: 72, borderRadius: 36, backgroundColor: c.surface, alignItems: "center", justifyContent: "center" },
  heroTitle: { fontFamily: fonts.extrabold, fontSize: 30, color: c.onBrandPrimary, marginTop: spacing.sm },
  heroSub: { fontFamily: fonts.medium, fontSize: 15, lineHeight: 21, color: c.onBrandPrimary, textAlign: "center" },
  body: { padding: spacing.xl, gap: spacing.lg },
  activeBox: { flexDirection: "row", gap: spacing.md, alignItems: "center", padding: spacing.lg, borderRadius: radius.lg, backgroundColor: c.successTint },
  perk: { flexDirection: "row", gap: spacing.md, alignItems: "flex-start" },
  perkIcon: { width: 44, height: 44, borderRadius: radius.md, backgroundColor: c.brandTertiary, alignItems: "center", justifyContent: "center" },
  plan: { flexDirection: "row", alignItems: "center", gap: spacing.md, padding: spacing.lg, borderRadius: radius.lg, borderWidth: 2, backgroundColor: c.surfaceSecondary },
  planLabel: { fontFamily: fonts.bold, fontSize: 16, color: c.onSurface },
  price: { fontFamily: fonts.extrabold, fontSize: 17, color: c.onSurface },
  per: { fontFamily: fonts.medium, fontSize: 12, color: c.muted },
  demo: { flexDirection: "row", gap: spacing.sm, alignItems: "center" },
  demoText: { flex: 1, fontFamily: fonts.medium, fontSize: 12, color: c.muted },
  topBar: { position: "absolute", left: spacing.lg },
  sticky: { position: "absolute", left: 0, right: 0, bottom: 0, paddingHorizontal: spacing.xl, paddingTop: spacing.md, backgroundColor: c.surface, borderTopWidth: 1, borderTopColor: c.divider },
}));
