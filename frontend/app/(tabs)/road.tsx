import { useQuery } from "@tanstack/react-query";
import * as Haptics from "expo-haptics";
import { useRouter } from "expo-router";
import { useEffect, useState } from "react";
import { ActivityIndicator, Modal, Pressable, RefreshControl, ScrollView, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, Milestone, PathsResponse, Roadmap, Task } from "@/src/api";
import { useAuth } from "@/src/auth";
import { milestoneDone, RoadMap } from "@/src/components/RoadMap";
import { MilestoneSheet, TaskSheet } from "@/src/components/TaskSheet";
import { Button, ErrorBox, IconButton, Ionicons, AiNote, Txt } from "@/src/components/ui";
import { usesNativeTabs } from "@/src/navigation";
import { queryClient } from "@/src/query-client";
import { maybeRequestReview } from "@/src/review";
import { playSuccess } from "@/src/sound";
import { fonts, makeStyles, radius, spacing, useTheme } from "@/src/theme";

export default function RoadScreen() {
  const insets = useSafeAreaInsets();
  const bottomChrome = usesNativeTabs ? insets.bottom : 0;
  const styles = useStyles();
  const { colors } = useTheme();
  const router = useRouter();
  const { t } = useAuth();
  const [taskId, setTaskId] = useState<string | null>(null);
  const [ms, setMs] = useState<{ m: Milestone; i: number } | null>(null);

  const q = useQuery({
    queryKey: ["roadmap"],
    queryFn: () => api<Roadmap>("/roadmap"),
    refetchInterval: (query) => (query.state.data?.status === "pending" ? 3000 : false),
  });
  const paths = useQuery({ queryKey: ["paths", q.data?.status, q.data?.path_id], queryFn: () => api<PathsResponse>("/paths") });
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const refreshAll = () => {
    queryClient.invalidateQueries({ queryKey: ["roadmap"] });
    queryClient.invalidateQueries({ queryKey: ["paths"] });
    queryClient.invalidateQueries({ queryKey: ["study-plan"] });
  };
  const switchPath = async (pathId: string) => {
    if (pathId === q.data?.path_id) return;
    await api(`/paths/${pathId}/activate`, { method: "POST" }).catch(() => {});
    refreshAll();
  };
  const deletePath = async () => {
    setDeleting(true);
    await api(`/paths/${q.data?.path_id}`, { method: "DELETE" }).catch(() => {});
    setDeleting(false);
    setConfirmDelete(false);
    refreshAll();
  };
  const data = q.data;
  const milestones = data?.milestones || [];
  const allTasks = milestones.flatMap((m) => m.tasks);
  const doneCount = allTasks.filter((t) => t.done).length;
  const pct = allTasks.length ? Math.round((doneCount / allTasks.length) * 100) : 0;
  const currentTask = taskId ? allTasks.find((t) => t.id === taskId) || null : null;
  const currentMs = ms ? milestones.find((m) => m.id === ms.m.id) || null : null;

  // Ask for a store rating at two positive, low-friction moments: the first time any
  // roadmap finishes building, and the first time a path reaches 100%. Each only ever
  // fires once (see src/review.ts), and both are capped/cooled-down together app-wide.
  useEffect(() => {
    if (data?.status === "ready") maybeRequestReview("first_roadmap");
  }, [data?.status]);
  useEffect(() => {
    if (data?.status === "ready" && allTasks.length > 0 && pct === 100) maybeRequestReview("path_complete");
  }, [pct, data?.status, allTasks.length]);

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
      queryClient.invalidateQueries({ queryKey: ["paths"] });
    } catch {
      queryClient.setQueryData(["roadmap"], prev);
    }
  };

  return (
    <View style={styles.root}>
      <View style={[styles.header, { paddingTop: insets.top + spacing.lg }]}>
        <View style={styles.titleRow}>
          <View style={{ flex: 1, gap: spacing.xs }}>
            <Txt variant="caption">{t.road.headerKicker}</Txt>
            <Txt variant="title" numberOfLines={2} testID="road-career-title">
              {data?.career?.title || t.road.titleFallback}
            </Txt>
          </View>
          {data?.path_id && (paths.data?.paths.length ?? 0) > 1 ? (
            <IconButton testID="road-delete-path" icon="trash-outline" onPress={() => setConfirmDelete(true)} />
          ) : null}
        </View>
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
        {data?.status === "ready" ? <AiNote style={{ marginTop: spacing.sm }} /> : null}
      </View>
      {data && data.status !== "none" ? (
        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.chipRow} contentContainerStyle={styles.chipContent}>
          <Pressable testID="road-open-plan" onPress={() => router.push("/plan")} style={[styles.action, { backgroundColor: colors.brandPrimary }]}>
            <Ionicons name="calendar-outline" size={16} color={colors.onBrandPrimary} />
            <Text style={[styles.actionText, { color: colors.onBrandPrimary }]}>{t.road.studyPlan}</Text>
          </Pressable>
          {(paths.data?.paths || []).map((p) => (
            <Pressable
              key={p.path_id}
              testID={`road-path-${p.path_id}`}
              onPress={() => switchPath(p.path_id)}
              style={[styles.action, p.path_id === data.path_id && { borderColor: colors.brandPrimary, backgroundColor: colors.brandTertiary }]}
            >
              <Text numberOfLines={1} style={[styles.actionText, { maxWidth: 160 }, p.path_id === data.path_id && { color: colors.onBrandTertiary }]}>
                {p.title}
              </Text>
              <Text style={styles.actionSub}>{p.progress}%</Text>
            </Pressable>
          ))}
        </ScrollView>
      ) : null}

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
            {t.road.emptyTitle}
          </Txt>
          <Txt style={{ textAlign: "center" }}>{t.road.emptyText}</Txt>
          <Button testID="road-go-matches" title={t.road.goToMatches} icon="briefcase" onPress={() => router.navigate("/(tabs)")} style={{ alignSelf: "stretch" }} />
        </View>
      ) : data?.status === "pending" ? (
        <View style={styles.empty} testID="road-building">
          <ActivityIndicator size="large" color={colors.brandPrimary} />
          <Txt variant="heading" style={{ textAlign: "center" }}>
            {t.road.buildingTitle}
          </Txt>
          <Txt style={{ textAlign: "center" }}>{t.road.buildingText}</Txt>
        </View>
      ) : data?.status === "error" ? (
        <View style={{ padding: spacing.xl }}>
          <ErrorBox testID="road-gen-error" message={t.road.genError} onRetry={() => router.navigate("/(tabs)")} />
        </View>
      ) : (
        <ScrollView
          testID="road-scroll"
          contentContainerStyle={{ paddingHorizontal: spacing.md, paddingBottom: bottomChrome + spacing.xl }}
          refreshControl={<RefreshControl refreshing={q.isRefetching} onRefresh={() => { q.refetch(); }} tintColor={colors.brandPrimary} />}
        >
          <View style={styles.hint}>
            <Ionicons name="information-circle-outline" size={18} color={colors.muted} />
            <Text style={styles.hintText}>{t.road.hint}</Text>
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
      <Modal visible={confirmDelete} transparent animationType="fade" onRequestClose={() => setConfirmDelete(false)}>
        <View style={styles.overlay}>
          <View style={styles.dialog} testID="road-delete-dialog">
            <Txt variant="heading">{t.road.deleteTitle}</Txt>
            <Txt>{t.road.deleteText(data?.career?.title)}</Txt>
            <Button testID="road-delete-confirm" title={t.road.deleteConfirm} onPress={deletePath} loading={deleting} />
            <Button testID="road-delete-cancel" title={t.road.deleteCancel} variant="ghost" onPress={() => setConfirmDelete(false)} />
          </View>
        </View>
      </Modal>
    </View>
  );
}

const useStyles = makeStyles((c) => ({
  root: { flex: 1, backgroundColor: c.surface },
  header: { paddingHorizontal: spacing.xl, paddingBottom: spacing.sm, gap: spacing.xs },
  titleRow: { flexDirection: "row", alignItems: "flex-start", gap: spacing.md },
  chipRow: { flexGrow: 0, flexShrink: 0, minHeight: 56, height: 56, borderBottomWidth: 1, borderBottomColor: c.divider },
  chipContent: { paddingHorizontal: spacing.xl, gap: spacing.sm, alignItems: "center" },
  action: {
    height: 36,
    flexShrink: 0,
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    paddingHorizontal: spacing.md,
    borderRadius: radius.pill,
    borderWidth: 1.5,
    borderColor: c.border,
    backgroundColor: c.surfaceSecondary,
  },
  actionText: { fontFamily: fonts.semibold, fontSize: 13, color: c.onSurface },
  actionSub: { fontFamily: fonts.bold, fontSize: 11, color: c.muted },
  overlay: { flex: 1, backgroundColor: c.overlay, alignItems: "center", justifyContent: "center", padding: spacing.xl },
  dialog: { width: "100%", backgroundColor: c.surface, borderRadius: radius.lg, padding: spacing.xl, gap: spacing.md },
  progressRow: { flexDirection: "row", alignItems: "center", gap: spacing.md, marginTop: spacing.sm },
  track: { flex: 1, height: 10, borderRadius: radius.pill, backgroundColor: c.surfaceTertiary, overflow: "hidden" },
  bar: { height: 10, borderRadius: radius.pill, backgroundColor: c.brandPrimary },
  pct: { fontFamily: fonts.extrabold, fontSize: 16, color: c.onSurface, minWidth: 44, textAlign: "right" },
  empty: { flex: 1, alignItems: "center", justifyContent: "center", padding: spacing.xl, gap: spacing.lg },
  emptyIcon: { width: 88, height: 88, borderRadius: 44, backgroundColor: c.brandTertiary, alignItems: "center", justifyContent: "center" },
  hint: { flexDirection: "row", gap: spacing.sm, alignItems: "center", paddingHorizontal: spacing.md, paddingTop: spacing.lg },
  hintText: { flex: 1, fontFamily: fonts.medium, fontSize: 13, color: c.muted },
}));
