import * as Haptics from "expo-haptics";
import { useRouter } from "expo-router";
import { useState } from "react";
import { ScrollView, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api } from "@/src/api";
import { useAuth } from "@/src/auth";
import { Button, Ionicons, IconName, PressableScale, Txt } from "@/src/components/ui";
import { usesNativeTabs } from "@/src/navigation";
import { queryClient } from "@/src/query-client";
import { fonts, makeStyles, radius, setThemeName, spacing, ThemeName, themeLabels, themes, useTheme } from "@/src/theme";

export default function Profile() {
  const insets = useSafeAreaInsets();
  const bottomChrome = usesNativeTabs ? insets.bottom : 0;
  const styles = useStyles();
  const { colors, name } = useTheme();
  const router = useRouter();
  const { user, logout } = useAuth();
  const [regen, setRegen] = useState(false);
  const [msg, setMsg] = useState("");

  const regenerate = async () => {
    setRegen(true);
    setMsg("");
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
              {user?.name || "Twój profil"}
            </Txt>
            <Txt variant="caption" testID="profile-email">
              {user?.email}
            </Txt>
          </View>
        </View>

        <View style={{ gap: spacing.md }}>
          <Txt variant="heading">Premium i doradca</Txt>
          {user?.role === "admin" ? (
            <Row icon="shield-checkmark-outline" title="Panel administratora" subtitle="Użytkownicy i darmowe Premium" testID="profile-admin" onPress={() => router.push("/admin")} />
          ) : null}
          <Row
            icon="diamond-outline"
            title={user?.is_premium ? "Masz Premium" : "Reset Premium"}
            subtitle={user?.is_premium ? "Zarządzaj subskrypcją" : "Do 3 ścieżek, plan nauki, czat bez limitu"}
            testID="profile-premium"
            onPress={() => router.push("/premium")}
          />
          <Row icon="chatbubbles-outline" title="Doradca kariery" subtitle="Zapytaj AI o swoją ścieżkę" testID="profile-chat" onPress={() => router.push("/chat")} />
          <Row icon="calendar-outline" title="Plan nauki" subtitle="Tydzień po tygodniu" testID="profile-plan" onPress={() => router.push("/plan")} />
        </View>

        <View style={{ gap: spacing.md }}>
          <Txt variant="heading">Styl aplikacji</Txt>
          {(Object.keys(themes) as ThemeName[]).map((t) => {
            const tc = themes[t];
            const active = t === name;
            return (
              <PressableScale
                key={t}
                testID={`theme-option-${t}`}
                onPress={() => {
                  Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Heavy).catch(() => {});
                  setThemeName(t);
                }}
                style={[styles.themeCard, { borderColor: active ? colors.brandPrimary : colors.border }]}
              >
                <View style={[styles.swatch, { backgroundColor: tc.surface, borderColor: tc.border }]}>
                  <View style={[styles.dot, { backgroundColor: tc.brandPrimary }]} />
                  <View style={[styles.dot, { backgroundColor: tc.brandTertiary }]} />
                  <View style={[styles.dot, { backgroundColor: tc.onSurface }]} />
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={styles.themeTitle}>{themeLabels[t].title}</Text>
                  <Txt variant="caption">{themeLabels[t].subtitle}</Txt>
                </View>
                <Ionicons name={active ? "radio-button-on" : "radio-button-off"} size={22} color={active ? colors.brandPrimary : colors.borderStrong} />
              </PressableScale>
            );
          })}
        </View>

        <View style={{ gap: spacing.md }}>
          <Txt variant="heading">Moje odpowiedzi</Txt>
          <Row icon="create-outline" title="Edytuj ankietę" subtitle="Zmień odpowiedzi i otrzymaj nowe propozycje" testID="profile-edit-quiz" onPress={() => router.push("/quiz?edit=1")} />
          <Row icon="sparkles-outline" title="Wygeneruj nowe propozycje" subtitle="AI ponownie przeanalizuje Twój profil" testID="profile-regenerate" onPress={regenerate} loading={regen} />
          {msg ? <Txt style={{ color: colors.error }}>{msg}</Txt> : null}
        </View>

        <Button testID="profile-logout-button" title="Wyloguj się" variant="ghost" icon="log-out-outline" onPress={async () => {
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
  return (
    <PressableScale testID={testID} onPress={onPress} disabled={loading} style={styles.row}>
      <View style={styles.rowIcon}>
        <Ionicons name={icon} size={22} color={colors.onBrandTertiary} />
      </View>
      <View style={{ flex: 1 }}>
        <Text style={styles.themeTitle}>{loading ? "Proszę czekać…" : title}</Text>
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
  row: { flexDirection: "row", alignItems: "center", gap: spacing.md, padding: spacing.md, borderRadius: radius.lg, backgroundColor: c.surfaceSecondary, minHeight: 64 },
  rowIcon: { width: 44, height: 44, borderRadius: radius.md, backgroundColor: c.brandTertiary, alignItems: "center", justifyContent: "center" },
}));
