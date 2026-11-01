import { LinearGradient } from "expo-linear-gradient";
import { useRouter } from "expo-router";
import { useState } from "react";
import { Modal, Pressable, ScrollView, Text, TextInput, View } from "react-native";
import Animated, { FadeInDown } from "react-native-reanimated";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api } from "@/src/api";
import { useAuth } from "@/src/auth";
import { Button, ErrorBox, IconButton, Ionicons, IconName, Txt } from "@/src/components/ui";
import { queryClient } from "@/src/query-client";
import { playSuccess } from "@/src/sound";
import { fonts, makeStyles, radius, spacing, useTheme } from "@/src/theme";

const PLANS = [
  { key: "monthly", label: "Miesięczny", price: "19 zł", per: "/ miesiąc", note: "Anuluj w każdej chwili" },
  { key: "yearly", label: "Roczny", price: "149,99 zł", per: "/ rok", note: "Tylko 12,50 zł miesięcznie · oszczędzasz 37%" },
] as const;

const PERKS: { icon: IconName; title: string; text: string }[] = [
  { icon: "eye-off", title: "Bez reklam", text: "Żadnych reklam przy ścieżkach, planie nauki ani w trakcie korzystania." },
  { icon: "trending-up", title: "25 nowych ścieżek miesięcznie", text: "Twórz do 25 nowych ścieżek kariery w miesiącu bez reklam — plan tygodniowy i dzienny do nich zawsze gratis, bez limitu." },
];

export default function Premium() {
  const insets = useSafeAreaInsets();
  const styles = useStyles();
  const { colors } = useTheme();
  const router = useRouter();
  const { user, refresh, t } = useAuth();
  const [plan, setPlan] = useState<"monthly" | "yearly">("yearly");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [confirmVisible, setConfirmVisible] = useState(false);
  const [reasonVisible, setReasonVisible] = useState(false);
  const [reason, setReason] = useState<string | null>(null);
  const [reasonDetail, setReasonDetail] = useState("");
  const [reasonError, setReasonError] = useState("");
  const active = !!user?.is_premium;
  const limit = user?.roadmap_generations_limit ?? 25;

  const REASONS: { key: string; label: string }[] = [
    { key: "too_expensive", label: t.premium.reasonTooExpensive },
    { key: "no_longer_needed", label: t.premium.reasonNoLongerNeeded },
    { key: "not_satisfied", label: t.premium.reasonNotSatisfied },
    { key: "got_job", label: t.premium.reasonGotJob },
    { key: "other", label: t.premium.reasonOther },
  ];

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

  const openReasonModal = () => {
    setConfirmVisible(false);
    setReason(null);
    setReasonDetail("");
    setReasonError("");
    setReasonVisible(true);
  };

  const confirmCancel = async () => {
    setLoading(true);
    setError("");
    try {
      await api("/premium/cancel", {
        method: "POST",
        body: { reason: reason || undefined, detail: reasonDetail.trim() || undefined },
      });
      setReasonVisible(false);
      await after();
    } catch (e: any) {
      setReasonError(e.message);
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
          <Text style={styles.heroSub}>Szybciej do nowego zawodu — ze ścieżką i planem na każdy dzień.</Text>
        </LinearGradient>

        <View style={styles.body}>
          {active ? (
            <View style={styles.activeBox} testID="premium-active">
              <Ionicons name="checkmark-circle" size={24} color={colors.success} />
              <View style={{ flex: 1 }}>
                <Txt variant="heading">Masz aktywne Premium</Txt>
                <Txt variant="caption" testID="premium-usage">
                  Wykorzystano {user?.roadmap_generations_used ?? 0} z {limit} nowych ścieżek w tym miesiącu
                </Txt>
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
          <Button testID="premium-cancel-button" title={t.premium.cancelButton} variant="ghost" onPress={() => setConfirmVisible(true)} loading={loading} />
        ) : (
          <Button testID="premium-subscribe-button" title={t.premium.subscribeButton} icon="diamond" onPress={subscribe} loading={loading} />
        )}
      </View>

      <Modal visible={confirmVisible} transparent animationType="fade" onRequestClose={() => setConfirmVisible(false)}>
        <View style={styles.overlay}>
          <View style={styles.dialog} testID="premium-cancel-confirm-dialog">
            <Ionicons name="alert-circle-outline" size={36} color={colors.brandPrimary} />
            <Txt variant="heading" style={{ textAlign: "center" }}>
              {t.premium.cancelConfirmTitle}
            </Txt>
            <Txt style={{ textAlign: "center" }}>{t.premium.cancelConfirmText(limit)}</Txt>
            <Button testID="premium-keep-button" title={t.premium.keepPremiumButton} onPress={() => setConfirmVisible(false)} style={{ alignSelf: "stretch" }} />
            <Button testID="premium-continue-cancel-button" title={t.premium.continueCancelButton} variant="ghost" onPress={openReasonModal} style={{ alignSelf: "stretch" }} />
          </View>
        </View>
      </Modal>

      <Modal visible={reasonVisible} transparent animationType="fade" onRequestClose={() => setReasonVisible(false)}>
        <View style={styles.overlay}>
          <View style={styles.dialog} testID="premium-cancel-reason-dialog">
            <Txt variant="heading" style={{ textAlign: "center" }}>
              {t.premium.reasonModalTitle}
            </Txt>
            <Txt variant="caption" style={{ textAlign: "center" }}>
              {t.premium.reasonModalSubtitle}
            </Txt>
            <View style={{ alignSelf: "stretch", gap: spacing.sm }}>
              {REASONS.map((r) => {
                const sel = reason === r.key;
                return (
                  <Pressable
                    key={r.key}
                    testID={`premium-cancel-reason-${r.key}`}
                    onPress={() => {
                      setReason(r.key);
                      setReasonError("");
                    }}
                    style={[styles.reasonRow, { borderColor: sel ? colors.brandPrimary : colors.border }]}
                  >
                    <Ionicons name={sel ? "radio-button-on" : "radio-button-off"} size={20} color={sel ? colors.brandPrimary : colors.borderStrong} />
                    <Text style={styles.reasonLabel}>{r.label}</Text>
                  </Pressable>
                );
              })}
              {reason === "other" ? (
                <TextInput
                  testID="premium-cancel-reason-detail"
                  value={reasonDetail}
                  onChangeText={setReasonDetail}
                  placeholder={t.premium.reasonOtherPlaceholder}
                  placeholderTextColor={colors.muted}
                  multiline
                  style={styles.reasonInput}
                />
              ) : null}
            </View>
            {reasonError ? <ErrorBox testID="premium-cancel-reason-error" message={reasonError} /> : null}
            <Button testID="premium-confirm-cancel-button" title={t.premium.confirmCancelButton} onPress={confirmCancel} loading={loading} style={{ alignSelf: "stretch" }} />
            <Button testID="premium-reason-dismiss-button" title={t.common.cancel} variant="ghost" onPress={() => setReasonVisible(false)} style={{ alignSelf: "stretch" }} />
          </View>
        </View>
      </Modal>
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
  overlay: { flex: 1, backgroundColor: "rgba(0,0,0,0.5)", alignItems: "center", justifyContent: "center", padding: spacing.xl },
  dialog: { width: "100%", maxWidth: 380, backgroundColor: c.surface, borderRadius: radius.lg, padding: spacing.xl, gap: spacing.md, alignItems: "center" },
  reasonRow: { flexDirection: "row", alignItems: "center", gap: spacing.sm, padding: spacing.md, borderRadius: radius.md, borderWidth: 2 },
  reasonLabel: { flex: 1, fontFamily: fonts.medium, fontSize: 14, color: c.onSurface },
  reasonInput: { borderWidth: 1, borderColor: c.border, borderRadius: radius.md, padding: spacing.md, fontFamily: fonts.medium, fontSize: 14, color: c.onSurface, minHeight: 60, textAlignVertical: "top" },
}));
