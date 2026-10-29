import { useQuery } from "@tanstack/react-query";
import { useRouter } from "expo-router";
import { useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, Text, View } from "react-native";
import Animated, { FadeInDown } from "react-native-reanimated";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, StudyPlan } from "@/src/api";
import { useAuth } from "@/src/auth";
import { Badge, Button, ErrorBox, IconButton, Ionicons, Txt } from "@/src/components/ui";
import { queryClient } from "@/src/query-client";
import { fonts, makeStyles, radius, spacing, useTheme } from "@/src/theme";

export default function PlanScreen() {
  const insets = useSafeAreaInsets();
  const styles = useStyles();
  const { colors } = useTheme();
  const router = useRouter();
  const { user } = useAuth();
  const [open, setOpen] = useState<number>(1);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState("");

  const q = useQuery({
    queryKey: ["study-plan"],
    queryFn: () => api<StudyPlan>("/roadmap/study-plan"),
    refetchInterval: (query) => (query.state.data?.status === "pending" ? 3000 : false),
  });

  const create = async () => {
    setStarting(true);
    setError("");
    try {
      await api("/roadmap/study-plan", { method: "POST" });
      queryClient.invalidateQueries({ queryKey: ["study-plan"] });
    } catch (e: any) {
      setError(e.message);
    } finally {
      setStarting(false);
    }
  };

  const data = q.data;
  const plan = data?.plan;

  return (
    <View style={styles.root}>
      <View style={[styles.header, { paddingTop: insets.top + spacing.sm }]}>
        <IconButton testID="plan-back-button" icon="arrow-back" onPress={() => (router.canGoBack() ? router.back() : router.replace("/(tabs)/road"))} />
        <View style={{ flex: 1 }}>
          <Txt variant="heading">Plan nauki</Txt>
          <Txt variant="caption" numberOfLines={1}>
            {data?.career?.title || "Tydzień po tygodniu"}
          </Txt>
        </View>
      </View>

      <ScrollView contentContainerStyle={{ padding: spacing.xl, gap: spacing.lg, paddingBottom: insets.bottom + spacing.xl }}>
        {!user?.is_premium ? (
          <View style={styles.upsell} testID="plan-upsell">
            <Ionicons name="calendar" size={36} color={colors.onBrandTertiary} />
            <Txt variant="title" style={{ textAlign: "center" }}>
              Plan nauki w Premium
            </Txt>
            <Txt style={{ textAlign: "center" }}>
              AI ułoży Ci 8-tygodniowy plan: co robić w każdym tygodniu, ile godzin i z jakich materiałów — dopasowany do Twojego czasu.
            </Txt>
            <Button testID="plan-go-premium" title="Odblokuj Premium" icon="diamond" onPress={() => router.push("/premium")} style={{ alignSelf: "stretch" }} />
          </View>
        ) : q.isLoading ? (
          <ActivityIndicator color={colors.brandPrimary} />
        ) : q.isError ? (
          <ErrorBox testID="plan-error" message={(q.error as Error).message} onRetry={() => q.refetch()} />
        ) : data?.status === "pending" ? (
          <View style={styles.center} testID="plan-pending">
            <ActivityIndicator size="large" color={colors.brandPrimary} />
            <Txt variant="heading">Układam Twój plan…</Txt>
            <Txt style={{ textAlign: "center" }}>To potrwa około minuty.</Txt>
          </View>
        ) : data?.status === "ready" && plan ? (
          <>
            <View style={styles.summary} testID="plan-summary">
              <Badge label={`ok. ${plan.hours_per_week} h tygodniowo`} />
              <Txt>{plan.summary}</Txt>
            </View>
            {plan.weeks.map((w, i) => {
              const isOpen = open === w.week;
              return (
                <Animated.View key={w.week} entering={FadeInDown.delay(i * 50)}>
                  <Pressable testID={`plan-week-${w.week}`} onPress={() => setOpen(isOpen ? 0 : w.week)} style={styles.week}>
                    <View style={styles.weekHead}>
                      <View style={styles.weekNum}>
                        <Text style={styles.weekNumText}>{w.week}</Text>
                      </View>
                      <View style={{ flex: 1 }}>
                        <Text style={styles.kicker}>TYDZIEŃ {w.week}</Text>
                        <Text style={styles.focus}>{w.focus}</Text>
                      </View>
                      <Ionicons name={isOpen ? "chevron-up" : "chevron-down"} size={20} color={colors.muted} />
                    </View>
                    {isOpen ? (
                      <View style={{ gap: spacing.md, marginTop: spacing.md }}>
                        <Txt variant="caption">Cel: {w.goal}</Txt>
                        {w.items.map((it, j) => (
                          <View key={j} style={styles.item}>
                            <Ionicons name="ellipse" size={8} color={colors.brandPrimary} style={{ marginTop: 7 }} />
                            <View style={{ flex: 1 }}>
                              <Text style={styles.itemTitle}>
                                {it.title} <Text style={styles.hours}>· {it.hours} h</Text>
                              </Text>
                              <Txt>{it.description}</Txt>
                            </View>
                          </View>
                        ))}
                      </View>
                    ) : null}
                  </Pressable>
                </Animated.View>
              );
            })}
            {plan.tips?.length ? (
              <View style={{ gap: spacing.sm }}>
                <Txt variant="heading">Rady na start</Txt>
                {plan.tips.map((t, i) => (
                  <View key={i} style={styles.item}>
                    <Ionicons name="bulb-outline" size={18} color={colors.brandPrimary} />
                    <Txt style={{ flex: 1 }}>{t}</Txt>
                  </View>
                ))}
              </View>
            ) : null}
            <Button testID="plan-regenerate-button" title="Ułóż nowy plan" variant="ghost" icon="refresh" onPress={create} loading={starting} />
          </>
        ) : (
          <View style={styles.center} testID="plan-empty">
            <Ionicons name="calendar-outline" size={44} color={colors.brandPrimary} />
            <Txt variant="title" style={{ textAlign: "center" }}>
              {data?.status === "error" ? "Spróbujmy jeszcze raz" : "Ułóż plan nauki"}
            </Txt>
            <Txt style={{ textAlign: "center" }}>Plan obejmie najbliższe punkty na Twojej drodze i Twój dostępny czas.</Txt>
            <Button testID="plan-create-button" title="Ułóż mój plan" icon="sparkles" onPress={create} loading={starting} style={{ alignSelf: "stretch" }} />
          </View>
        )}
        {error ? <ErrorBox testID="plan-create-error" message={error} /> : null}
      </ScrollView>
    </View>
  );
}

const useStyles = makeStyles((c) => ({
  root: { flex: 1, backgroundColor: c.surface },
  header: { flexDirection: "row", alignItems: "center", gap: spacing.md, paddingHorizontal: spacing.lg, paddingBottom: spacing.md, borderBottomWidth: 1, borderBottomColor: c.divider },
  upsell: { alignItems: "center", gap: spacing.md, padding: spacing.xl, borderRadius: radius.lg, backgroundColor: c.brandTertiary },
  center: { alignItems: "center", gap: spacing.md, paddingVertical: spacing.xxl },
  summary: { gap: spacing.sm, padding: spacing.lg, borderRadius: radius.lg, backgroundColor: c.surfaceSecondary },
  week: { padding: spacing.lg, borderRadius: radius.lg, backgroundColor: c.surfaceSecondary, borderWidth: 1, borderColor: c.border },
  weekHead: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  weekNum: { width: 40, height: 40, borderRadius: 20, backgroundColor: c.brandPrimary, alignItems: "center", justifyContent: "center" },
  weekNumText: { fontFamily: fonts.extrabold, fontSize: 16, color: c.onBrandPrimary },
  kicker: { fontFamily: fonts.bold, fontSize: 10, letterSpacing: 1, color: c.brandPrimary },
  focus: { fontFamily: fonts.bold, fontSize: 15, color: c.onSurface },
  item: { flexDirection: "row", gap: spacing.sm, alignItems: "flex-start" },
  itemTitle: { fontFamily: fonts.bold, fontSize: 14, color: c.onSurface },
  hours: { fontFamily: fonts.medium, color: c.muted },
}));
