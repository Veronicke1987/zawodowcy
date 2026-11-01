import * as Haptics from "expo-haptics";
import { useRouter } from "expo-router";
import { useState } from "react";
import { ActivityIndicator, ScrollView, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api } from "@/src/api";
import { useAds } from "@/src/ads/AdsProvider";
import { useAuth } from "@/src/auth";
import { Button, Ionicons, IconName, PressableScale, Txt } from "@/src/components/ui";
import { COUNTRIES } from "@/src/countries";
import { StreakCard } from "@/src/components/Streak";
import { usesNativeTabs } from "@/src/navigation";
import { queryClient } from "@/src/query-client";
import { fonts, makeStyles, radius, setThemeName, spacing, ThemeName, themeLabels, themes, useTheme } from "@/src/theme";


export default function Profile() {
  const insets = useSafeAreaInsets();
  const bottomChrome = usesNativeTabs ? insets.bottom : 0;
  const styles = useStyles();
  const { colors, name } = useTheme();
  const router = useRouter();
  const { user, logout, refresh, t, lang } = useAuth();
  const { watchAd, showAds } = useAds();
  const [regen, setRegen] = useState(false);
  const [msg, setMsg] = useState("");
  const [savingCountry, setSavingCountry] = useState<string | null>(null);

  const selectCountry = async (code: string) => {
    if (savingCountry || code === (user?.country || "PL")) return;
    setMsg("");
    setSavingCountry(code);
    try {
      await api("/account/country", { method: "PATCH", body: { country: code } });
      await refresh();
      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium).catch(() => {});
    } catch (e: any) {
      setMsg(e.message);
    } finally {
      setSavingCountry(null);
    }
  };

  const regenerate = async () => {
    setMsg("");
    if (!(await watchAd(t.ads.reasonRegenerateCareers))) return;
    setRegen(true);
    try {
      await api("/recommendations/generate", { method: "POST" });
      queryClient.invalidateQueries({ queryKey: ["recommendations"] });
      router.navigate("/(tabs)");
    } catch (e: any) {
      setMsg(e.message);
    } finally {
      setRegen(false);
    }
  };

  return (
    <View style={styles.root}>
      <ScrollView contentContainerStyle={{ paddingTop: insets.top + spacing.lg, paddingHorizontal: spacing.xl, paddingBottom: bottomChrome + spacing.xl, gap: spacing.xl }}>
        <View style={styles.userRow}>
          <View style={styles.avatar}>
            <Text style={styles.avatarText}>{(user?.name || user?.email || "?").charAt(0).toUpperCase()}</Text>
          </View>
          <View style={{ flex: 1 }}>
            <Txt variant="title" testID="profile-name">
              {user?.name || t.profile.titleFallback}
            </Txt>
            <Txt variant="caption" testID="profile-email">
              {user?.email}
            </Txt>
          </View>
        </View>

        <StreakCard />

        <View style={{ gap: spacing.md }}>
          <Txt variant="heading">{t.profile.premiumHeading}</Txt>
          {user?.role === "admin" ? (
            <Row icon="shield-checkmark-outline" title={t.profile.adminRow} subtitle={t.profile.adminSub} testID="profile-admin" onPress={() => router.push("/admin")} />
          ) : null}
          <Row
            icon="diamond-outline"
            title={user?.is_premium ? t.profile.premiumActiveTitle : `${t.common.appName} Premium`}
            subtitle={user?.is_premium ? t.profile.premiumActiveSub : t.profile.premiumInactiveSub}
            testID="profile-premium"
            onPress={() => router.push("/premium")}
          />
          <Row icon="calendar-outline" title={t.profile.planRow} subtitle={t.profile.planRowSub} testID="profile-plan" onPress={() => router.push("/plan")} />
        </View>

        <View style={{ gap: spacing.md }}>
          <Txt variant="heading">{t.profile.countryHeading}</Txt>
          <Txt variant="caption">{t.profile.countrySub}</Txt>
          {COUNTRIES.map((c) => {
            const active = (user?.country || "PL") === c.code;
            const saving = savingCountry === c.code;
            return (
              <PressableScale
                key={c.code}
                testID={`country-option-${c.code}`}
                onPress={() => selectCountry(c.code)}
                disabled={!!savingCountry}
                style={[styles.themeCard, { borderColor: active ? colors.brandPrimary : colors.border }]}
              >
                <Text style={styles.flag}>{c.flag}</Text>
                <View style={{ flex: 1 }}>
                  <Text style={styles.themeTitle}>{c.names[lang]}</Text>
                  <Txt variant="caption">
                    {t.profile.langSuffix} {c.langNames[lang]}
                  </Txt>
                </View>
                {saving ? (
                  <ActivityIndicator color={colors.brandPrimary} size="small" />
                ) : (
                  <Ionicons name={active ? "radio-button-on" : "radio-button-off"} size={22} color={active ? colors.brandPrimary : colors.borderStrong} />
                )}
              </PressableScale>
            );
          })}
        </View>

        <View style={{ gap: spacing.md }}>
          <Txt variant="heading">{t.profile.styleHeading}</Txt>
          {(Object.keys(themes) as ThemeName[]).map((th) => {
            const tc = themes[th];
            const active = th === name;
            return (
              <PressableScale
                key={th}
                testID={`theme-option-${th}`}
                onPress={() => {
                  Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Heavy).catch(() => {});
                  setThemeName(th);
                }}
                style={[styles.themeCard, { borderColor: active ? colors.brandPrimary : colors.border }]}
              >
                <View style={[styles.swatch, { backgroundColor: tc.surface, borderColor: tc.border }]}>
                  <View style={[styles.dot, { backgroundColor: tc.brandPrimary }]} />
                  <View style={[styles.dot, { backgroundColor: tc.brandTertiary }]} />
                  <View style={[styles.dot, { backgroundColor: tc.onSurface }]} />
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={styles.themeTitle}>{themeLabels[th].title}</Text>
                  <Txt variant="caption">{themeLabels[th].subtitle}</Txt>
                </View>
                <Ionicons name={active ? "radio-button-on" : "radio-button-off"} size={22} color={active ? colors.brandPrimary : colors.borderStrong} />
              </PressableScale>
            );
          })}
        </View>

        <View style={{ gap: spacing.md }}>
          <Txt variant="heading">{t.profile.answersHeading}</Txt>
          <Row icon="create-outline" title={t.profile.editQuiz} subtitle={t.profile.editQuizSub} testID="profile-edit-quiz" onPress={() => router.push("/quiz?edit=1")} />
          <Row icon="sparkles-outline" title={t.profile.regenerate} subtitle={t.profile.regenerateSub} testID="profile-regenerate" onPress={regenerate} loading={regen} />
          {showAds ? (
            <Txt variant="caption" testID="profile-ad-notice">
              {t.profile.adNotice}
            </Txt>
          ) : null}
          {msg ? <Txt style={{ color: colors.error }}>{msg}</Txt> : null}
        </View>

        <Button testID="profile-logout-button" title={t.profile.logout} variant="ghost" icon="log-out-outline" onPress={async () => {
          await logout();
          router.replace("/auth");
        }} />
      </ScrollView>
    </View>
  );
}

function Row({ icon, title, subtitle, onPress, testID, loading }: { icon: IconName; title: string; subtitle: string; onPress: () => void; testID: string; loading?: boolean }) {
  const styles = useStyles();
  const { colors } = useTheme();
  const { t } = useAuth();
  return (
    <PressableScale testID={testID} onPress={onPress} disabled={loading} style={styles.row}>
      <View style={styles.rowIcon}>
        <Ionicons name={icon} size={22} color={colors.onBrandTertiary} />
      </View>
      <View style={{ flex: 1 }}>
        <Text style={styles.themeTitle}>{loading ? t.profile.regeneratePleaseWait : title}</Text>
        <Txt variant="caption">{subtitle}</Txt>
      </View>
      <Ionicons name="chevron-forward" size={18} color={colors.muted} />
    </PressableScale>
  );
}

const useStyles = makeStyles((c) => ({
  root: { flex: 1, backgroundColor: c.surface },
  userRow: { flexDirection: "row", alignItems: "center", gap: spacing.lg },
  avatar: { width: 64, height: 64, borderRadius: 32, backgroundColor: c.brandPrimary, alignItems: "center", justifyContent: "center" },
  avatarText: { fontFamily: fonts.extrabold, fontSize: 26, color: c.onBrandPrimary },
  themeCard: { flexDirection: "row", alignItems: "center", gap: spacing.md, padding: spacing.md, borderRadius: radius.lg, borderWidth: 2, backgroundColor: c.surfaceSecondary },
  swatch: { width: 64, height: 48, borderRadius: radius.md, borderWidth: 1, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 4 },
  dot: { width: 14, height: 14, borderRadius: 7 },
  themeTitle: { fontFamily: fonts.bold, fontSize: 15, color: c.onSurface },
  flag: { fontSize: 28 },
  row: { flexDirection: "row", alignItems: "center", gap: spacing.md, padding: spacing.md, borderRadius: radius.lg, backgroundColor: c.surfaceSecondary, minHeight: 64 },
  rowIcon: { width: 44, height: 44, borderRadius: radius.md, backgroundColor: c.brandTertiary, alignItems: "center", justifyContent: "center" },
}));
