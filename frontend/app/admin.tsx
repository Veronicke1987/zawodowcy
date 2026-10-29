import { useQuery } from "@tanstack/react-query";
import { useRouter } from "expo-router";
import { useState } from "react";
import { ActivityIndicator, FlatList, Pressable, RefreshControl, Switch, Text, TextInput, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api } from "@/src/api";
import { useAuth } from "@/src/auth";
import { Badge, Button, ErrorBox, IconButton, Ionicons, Txt } from "@/src/components/ui";
import { fonts, makeStyles, radius, spacing, useTheme } from "@/src/theme";

type AdminUser = { id: string; email: string; name: string; role: string; is_premium: boolean; premium_plan?: string; created_at: string };
type Stats = { users: number; premium: number; gifted: number; pending_grants: number; paths: number };

export default function AdminPanel() {
  const insets = useSafeAreaInsets();
  const styles = useStyles();
  const { colors } = useTheme();
  const router = useRouter();
  const { user } = useAuth();
  const [search, setSearch] = useState("");
  const [email, setEmail] = useState("");
  const [granting, setGranting] = useState(false);
  const [msg, setMsg] = useState<{ text: string; ok: boolean } | null>(null);

  const stats = useQuery({ queryKey: ["admin-stats"], queryFn: () => api<Stats>("/admin/stats"), enabled: user?.role === "admin" });
  const list = useQuery({
    queryKey: ["admin-users", search],
    queryFn: () => api<{ users: AdminUser[]; pending: { email: string }[] }>(`/admin/users?q=${encodeURIComponent(search)}`),
    enabled: user?.role === "admin",
  });

  const reload = () => {
    stats.refetch();
    list.refetch();
  };

  const grant = async () => {
    setGranting(true);
    setMsg(null);
    try {
      const r = await api<{ message: string }>("/admin/premium/grant", { method: "POST", body: { email } });
      setMsg({ text: r.message, ok: true });
      setEmail("");
      reload();
    } catch (e: any) {
      setMsg({ text: e.message, ok: false });
    } finally {
      setGranting(false);
    }
  };

  const toggle = async (u: AdminUser, active: boolean) => {
    try {
      await api(`/admin/users/${u.id}/premium`, { method: "POST", body: { active } });
    } catch (e: any) {
      setMsg({ text: e.message, ok: false });
    }
    reload();
  };

  const removePending = async (e: string) => {
    await api(`/admin/premium/grant/${encodeURIComponent(e)}`, { method: "DELETE" }).catch(() => {});
    reload();
  };

  if (user?.role !== "admin") {
    return (
      <View style={[styles.root, { padding: spacing.xl, paddingTop: insets.top + spacing.xl, gap: spacing.lg }]}>
        <ErrorBox testID="admin-forbidden" message="Brak uprawnień administratora." />
        <Button testID="admin-forbidden-back" title="Wróć" variant="ghost" onPress={() => (router.canGoBack() ? router.back() : router.replace("/"))} />
      </View>
    );
  }

  return (
    <View style={styles.root}>
      <View style={[styles.header, { paddingTop: insets.top + spacing.sm }]}>
        <IconButton testID="admin-back-button" icon="arrow-back" onPress={() => (router.canGoBack() ? router.back() : router.replace("/(tabs)/profile"))} />
        <View style={{ flex: 1 }}>
          <Txt variant="heading">Panel administratora</Txt>
          <Txt variant="caption">{user.email}</Txt>
        </View>
      </View>

      <FlatList
        testID="admin-users-list"
        data={list.data?.users || []}
        keyExtractor={(u) => u.id}
        keyboardShouldPersistTaps="handled"
        refreshControl={<RefreshControl refreshing={list.isRefetching} onRefresh={reload} tintColor={colors.brandPrimary} />}
        contentContainerStyle={{ padding: spacing.xl, gap: spacing.sm, paddingBottom: insets.bottom + spacing.xl }}
        ListHeaderComponent={
          <View style={{ gap: spacing.lg, marginBottom: spacing.sm }}>
            <View style={styles.stats}>
              {[
                ["Użytkownicy", stats.data?.users],
                ["Premium", stats.data?.premium],
                ["Podarowane", stats.data?.gifted],
                ["Ścieżki", stats.data?.paths],
              ].map(([label, val]) => (
                <View key={label as string} style={styles.stat} testID={`admin-stat-${label}`}>
                  <Text style={styles.statNum}>{val ?? "–"}</Text>
                  <Text style={styles.statLbl}>{label}</Text>
                </View>
              ))}
            </View>

            <View style={styles.card}>
              <Txt variant="heading">Podaruj Premium</Txt>
              <Txt variant="caption">Wpisz e-mail. Jeśli osoba nie ma jeszcze konta, Premium włączy się po jej rejestracji.</Txt>
              <TextInput
                testID="admin-grant-email-input"
                value={email}
                onChangeText={setEmail}
                placeholder="adres@email.pl"
                placeholderTextColor={colors.muted}
                autoCapitalize="none"
                keyboardType="email-address"
                autoCorrect={false}
                style={styles.input}
              />
              <Button testID="admin-grant-button" title="Nadaj Premium" icon="gift" onPress={grant} loading={granting} disabled={!email.includes("@")} />
              {msg ? (
                <Text testID="admin-grant-message" style={[styles.msg, { color: msg.ok ? colors.success : colors.error }]}>
                  {msg.text}
                </Text>
              ) : null}
            </View>

            {list.data?.pending?.length ? (
              <View style={{ gap: spacing.sm }}>
                <Txt variant="heading">Czekają na rejestrację</Txt>
                {list.data.pending.map((p) => (
                  <View key={p.email} style={styles.row}>
                    <Ionicons name="time-outline" size={20} color={colors.muted} />
                    <Text style={[styles.email, { flex: 1 }]}>{p.email}</Text>
                    <Pressable testID={`admin-pending-remove-${p.email}`} onPress={() => removePending(p.email)} hitSlop={10}>
                      <Ionicons name="close-circle" size={22} color={colors.muted} />
                    </Pressable>
                  </View>
                ))}
              </View>
            ) : null}

            <Txt variant="heading">Użytkownicy</Txt>
            <TextInput
              testID="admin-search-input"
              value={search}
              onChangeText={setSearch}
              placeholder="Szukaj po e-mailu lub imieniu"
              placeholderTextColor={colors.muted}
              autoCapitalize="none"
              style={styles.input}
            />
            {list.isLoading ? <ActivityIndicator color={colors.brandPrimary} /> : null}
          </View>
        }
        renderItem={({ item }) => (
          <View style={styles.row} testID={`admin-user-${item.email}`}>
            <View style={{ flex: 1, gap: 4 }}>
              <Text style={styles.email} numberOfLines={1}>
                {item.email || "(bez e-maila)"}
              </Text>
              <View style={{ flexDirection: "row", gap: spacing.xs, flexWrap: "wrap" }}>
                {item.name ? <Txt variant="caption">{item.name}</Txt> : null}
                {item.role === "admin" ? <Badge label="Admin" /> : null}
                {item.is_premium ? <Badge label={item.premium_plan === "gift" ? "Premium (podarowane)" : "Premium"} tone="success" /> : null}
              </View>
            </View>
            <Switch
              testID={`admin-premium-switch-${item.email}`}
              value={item.is_premium}
              onValueChange={(v) => toggle(item, v)}
              trackColor={{ true: colors.brandPrimary, false: colors.surfaceTertiary }}
            />
          </View>
        )}
        ListEmptyComponent={list.isLoading ? null : <Txt>Brak użytkowników.</Txt>}
      />
    </View>
  );
}

const useStyles = makeStyles((c) => ({
  root: { flex: 1, backgroundColor: c.surface },
  header: { flexDirection: "row", alignItems: "center", gap: spacing.md, paddingHorizontal: spacing.lg, paddingBottom: spacing.md, borderBottomWidth: 1, borderBottomColor: c.divider },
  stats: { flexDirection: "row", gap: spacing.sm },
  stat: { flex: 1, padding: spacing.md, borderRadius: radius.md, backgroundColor: c.brandTertiary, alignItems: "center" },
  statNum: { fontFamily: fonts.extrabold, fontSize: 20, color: c.onBrandTertiary },
  statLbl: { fontFamily: fonts.medium, fontSize: 11, color: c.onBrandTertiary },
  card: { gap: spacing.md, padding: spacing.lg, borderRadius: radius.lg, backgroundColor: c.surfaceSecondary, borderWidth: 1, borderColor: c.border },
  input: {
    minHeight: 48,
    borderRadius: radius.md,
    backgroundColor: c.surface,
    borderWidth: 1,
    borderColor: c.border,
    paddingHorizontal: spacing.lg,
    fontFamily: fonts.medium,
    fontSize: 15,
    color: c.onSurface,
  },
  msg: { fontFamily: fonts.semibold, fontSize: 13 },
  row: { flexDirection: "row", alignItems: "center", gap: spacing.md, padding: spacing.md, borderRadius: radius.md, backgroundColor: c.surfaceSecondary, minHeight: 60 },
  email: { fontFamily: fonts.bold, fontSize: 14, color: c.onSurface },
}));
