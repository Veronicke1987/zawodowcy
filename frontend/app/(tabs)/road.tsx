import { useQuery } from "@tanstack/react-query";
import * as Haptics from "expo-haptics";
import { useRouter } from "expo-router";
import { useState } from "react";
import { ActivityIndicator, RefreshControl, ScrollView, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, Milestone, Roadmap, Task } from "@/src/api";
import { milestoneDone, RoadMap } from "@/src/components/RoadMap";
import { MilestoneSheet, TaskSheet } from "@/src/components/TaskSheet";
import { Button, ErrorBox, Ionicons, Txt } from "@/src/components/ui";
import { usesNativeTabs } from "@/src/navigation";
import { queryClient } from "@/src/query-client";
import { playSuccess } from "@/src/sound";
import { fonts, makeStyles, radius, spacing, useTheme } from "@/src/theme";

export default function RoadScreen() {
  const insets = useSafeAreaInsets();
  const bottomChrome = usesNativeTabs ? insets.bottom : 0;
  const styles = useStyles();
  const { colors } = useTheme();
  const router = useRouter();
  const [taskId, setTaskId] = useState<string | null>(null);
  const [ms, setMs] = useState<{ m: Milestone; i: number } | null>(null);

  const q = useQuery({
    queryKey: ["roadmap"],
    queryFn: () => api<Roadmap>("/roadmap"),
    refetchInterval: (query) => (query.state.data?.status === "pending" ? 3000 : false),
  });
  const data = q.data;
  const milestones = data?.milestones || [];
  const allTasks = milestones.flatMap((m) => m.tasks);
  const doneCount = allTasks.filter((t) => t.done).length;
  const pct = allTasks.length ? Math.round((doneCount / allTasks.length) * 100) : 0;
  const currentTask = taskId ? allTasks.find((t) => t.id === taskId) || null : null;
  const currentMs = ms ? milestones.find((m) => m.id === ms.m.id) || null : null;

  const toggle = async (t: Task) => {
    const next = !t.done;
    const prev = queryClient.getQueryData<Roadmap>(["roadmap"]);
    if (!prev) return;
    const updated: Roadmap = {
      ...prev,
      milestones: prev.milestones!.map((m) => ({ ...m, tasks: m.tasks.map((x) => (x.id === t.id ? { ...x, done: next } : x)) })),
    };
    queryClient.setQueryData(["roadmap"], updated);
    const parentBefore = prev.milestones!.find((m) => m.tasks.some((x) => x.id === t.id))!;
    const parentAfter = updated.milestones!.find((m) => m.id === parentBefore.id)!;
    if (next && !milestoneDone(parentBefore) && milestoneDone(parentAfter)) playSuccess();
    else Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium).catch(() => {});
    try {
      await api(`/roadmap/tasks/${t.id}`, { method: "PATCH", body: { done: next } });
    } catch {
      queryClient.setQueryData(["roadmap"], prev);
    }
  };

  return (
    <View style={styles.root}>
      <View style={[styles.header, { paddingTop: insets.top + spacing.lg }]}>
        <Txt variant="caption">TWOJA DROGA</Txt>
        <Txt variant="title" numberOfLines={2} testID="road-career-title">
          {data?.career?.title || "Ścieżka kariery"}
        </Txt>
        {data?.status === "ready" ? (
          <View style={styles.progressRow}>
            <View style={styles.track}>
              <View style={[styles.bar, { width: `${pct}%` }]} />
            </View>
            <Text style={styles.pct} testID="road-progress">
              {pct}%
            </Text>
          </View>
        ) : null}
      </View>

      {q.isLoading ? (
        <ActivityIndicator style={{ marginTop: spacing.xxl }} color={colors.brandPrimary} />
      ) : q.isError ? (
        <View style={{ padding: spacing.xl }}>
          <ErrorBox testID="road-error" message={(q.error as Error).message} onRetry={() => q.refetch()} />
        </View>
      ) : data?.status === "none" ? (
        <View style={styles.empty} testID="road-empty">
          <View style={styles.emptyIcon}>
            <Ionicons name="map" size={40} color={colors.onBrandTertiary} />
          </View>
          <Txt variant="title" style={{ textAlign: "center" }}>
            Wybierz swój cel
          </Txt>
          <Txt style={{ textAlign: "center" }}>Otwórz jeden z proponowanych zawodów i kliknij „Wybieram tę ścieżkę”, a zbudujemy Ci drogę krok po kroku.</Txt>
          <Button testID="road-go-matches" title="Zobacz zawody" icon="briefcase" onPress={() => router.navigate("/(tabs)")} style={{ alignSelf: "stretch" }} />
        </View>
      ) : data?.status === "pending" ? (
        <View style={styles.empty} testID="road-building">
          <ActivityIndicator size="large" color={colors.brandPrimary} />
          <Txt variant="heading" style={{ textAlign: "center" }}>
            Buduję Twoją drogę…
          </Txt>
          <Txt style={{ textAlign: "center" }}>AI analizuje wymagania z ofert pracy na każdym poziomie kariery. To potrwa około minuty.</Txt>
        </View>
      ) : data?.status === "error" ? (
        <View style={{ padding: spacing.xl }}>
          <ErrorBox testID="road-gen-error" message="Nie udało się zbudować drogi. Wybierz ścieżkę ponownie." onRetry={() => router.navigate("/(tabs)")} />
        </View>
      ) : (
        <ScrollView
          testID="road-scroll"
          contentContainerStyle={{ paddingHorizontal: spacing.md, paddingBottom: bottomChrome + spacing.xl }}
          refreshControl={<RefreshControl refreshing={q.isRefetching} onRefresh={() => q.refetch()} tintColor={colors.brandPrimary} />}
        >
          <View style={styles.hint}>
            <Ionicons name="information-circle-outline" size={18} color={colors.muted} />
            <Text style={styles.hintText}>Dotknij punktu na drodze, aby zobaczyć podpowiedzi, linki i kursy.</Text>
          </View>
          <RoadMap milestones={milestones} onTask={(t) => setTaskId(t.id)} onMilestone={(m, i) => setMs({ m, i })} />
        </ScrollView>
      )}

      <MilestoneSheet
        milestone={taskId ? null : currentMs}
        index={ms?.i ?? 0}
        onClose={() => setMs(null)}
        onTask={(t) => setTaskId(t.id)}
      />
      <TaskSheet task={currentTask} onClose={() => setTaskId(null)} onToggle={toggle} />
    </View>
  );
}

const useStyles = makeStyles((c) => ({
  root: { flex: 1, backgroundColor: c.surface },
  header: { paddingHorizontal: spacing.xl, paddingBottom: spacing.md, gap: spacing.xs, borderBottomWidth: 1, borderBottomColor: c.divider },
  progressRow: { flexDirection: "row", alignItems: "center", gap: spacing.md, marginTop: spacing.sm },
  track: { flex: 1, height: 10, borderRadius: radius.pill, backgroundColor: c.surfaceTertiary, overflow: "hidden" },
  bar: { height: 10, borderRadius: radius.pill, backgroundColor: c.brandPrimary },
  pct: { fontFamily: fonts.extrabold, fontSize: 16, color: c.onSurface, minWidth: 44, textAlign: "right" },
  empty: { flex: 1, alignItems: "center", justifyContent: "center", padding: spacing.xl, gap: spacing.lg },
  emptyIcon: { width: 88, height: 88, borderRadius: 44, backgroundColor: c.brandTertiary, alignItems: "center", justifyContent: "center" },
  hint: { flexDirection: "row", gap: spacing.sm, alignItems: "center", paddingHorizontal: spacing.md, paddingTop: spacing.lg },
  hintText: { flex: 1, fontFamily: fonts.medium, fontSize: 13, color: c.muted },
}));
