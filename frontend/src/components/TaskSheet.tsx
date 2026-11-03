import { useQuery } from "@tanstack/react-query";
import * as WebBrowser from "expo-web-browser";
import { useState } from "react";
import { ActivityIndicator, Modal, Pressable, ScrollView, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { useContentUnlock } from "@/src/ads/useContentUnlock";
import { api, Milestone, Resource, Task, TaskResources } from "@/src/api";
import { useAuth } from "@/src/auth";
import { AdUnlockGate, AiNote, Button, ErrorBox, IconButton, Ionicons, IconName, PressableScale, Txt } from "@/src/components/ui";
import { fonts, makeStyles, radius, spacing, useTheme } from "@/src/theme";

const TYPE_ICON: Record<string, IconName> = {
  youtube: "logo-youtube",
  course: "laptop-outline",
  studies: "school-outline",
  urzad_pracy: "business-outline",
  webinar: "videocam-outline",
  certificate: "ribbon-outline",
  article: "newspaper-outline",
};

export function Sheet({ visible, onClose, children, testID }: { visible: boolean; onClose: () => void; children: React.ReactNode; testID: string }) {
  const styles = useTaskSheetStyles();
  const insets = useSafeAreaInsets();
  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose} statusBarTranslucent>
      <View style={styles.backdrop}>
        <Pressable style={{ flex: 1 }} onPress={onClose} testID={`${testID}-backdrop`} />
        <View style={[styles.sheet, { paddingBottom: insets.bottom + spacing.lg }]} testID={testID}>
          <View style={styles.handle} />
          {children}
        </View>
      </View>
    </Modal>
  );
}

export function TaskSheet({ task, onClose, onToggle }: { task: Task | null; onClose: () => void; onToggle: (t: Task) => void }) {
  const styles = useTaskSheetStyles();
  const { colors } = useTheme();
  const { t } = useAuth();
  const [unlocking, setUnlocking] = useState(false);
  const { unlocked, checking, unlock } = useContentUnlock(task ? `task:${task.id}` : null, t.ads.reasonTaskResources);
  const q = useQuery({
    queryKey: ["resources", task?.id],
    queryFn: () => api<TaskResources>(`/roadmap/tasks/${task!.id}/resources`),
    enabled: !!task && unlocked,
    staleTime: Infinity,
  });
  const r = q.data;
  const handleUnlock = async () => {
    setUnlocking(true);
    try {
      await unlock();
    } finally {
      setUnlocking(false);
    }
  };
  return (
    <Sheet visible={!!task} onClose={onClose} testID="task-sheet">
      {task ? (
        <>
          <View style={styles.headRow}>
            <View style={{ flex: 1, gap: 4 }}>
              <Text style={styles.kicker}>{t.road.stepKicker}</Text>
              <Txt variant="title" testID="task-sheet-title">
                {task.title}
              </Txt>
            </View>
            <IconButton testID="task-sheet-close" icon="close" onPress={onClose} />
          </View>
          <ScrollView style={{ flexShrink: 1 }} contentContainerStyle={{ gap: spacing.lg, paddingBottom: spacing.lg }} showsVerticalScrollIndicator={false}>
            <Txt>{task.description}</Txt>
            <Button
              testID="task-toggle-button"
              title={task.done ? t.road.markDoneUndo : t.road.markDone}
              icon={task.done ? "checkmark-circle" : "checkmark-circle-outline"}
              variant={task.done ? "secondary" : "primary"}
              onPress={() => onToggle(task)}
            />
            {!unlocked ? (
              checking ? (
                <View style={styles.loading} testID="task-unlock-checking">
                  <ActivityIndicator color={colors.brandPrimary} />
                </View>
              ) : (
                <AdUnlockGate testID="task-unlock-gate" onUnlock={handleUnlock} loading={unlocking} />
              )
            ) : q.isLoading ? (
              <View style={styles.loading} testID="task-resources-loading">
                <ActivityIndicator color={colors.brandPrimary} />
                <Txt style={{ flex: 1 }}>{t.road.loadingResources}</Txt>
              </View>
            ) : q.isError ? (
              <ErrorBox testID="task-resources-error" message={(q.error as Error).message} onRetry={() => q.refetch()} />
            ) : r ? (
              <View style={{ gap: spacing.lg }} testID="task-resources">
                <Txt>{r.overview}</Txt>
                {r.time_estimate ? (
                  <View style={styles.pill}>
                    <Ionicons name="time-outline" size={16} color={colors.onBrandTertiary} />
                    <Text style={styles.pillText}>{r.time_estimate}</Text>
                  </View>
                ) : null}
                <Block title={t.road.howToGetIt} items={r.steps} numbered />
                {r.free_tips?.length ? <Block title={t.road.freeOrCheaper} items={r.free_tips} icon="gift-outline" /> : null}
                {r.specializations?.length ? <Block title={t.road.possibleSpecializations} items={r.specializations} icon="git-branch-outline" /> : null}
                <Txt variant="heading">{t.road.linksAndMaterials}</Txt>
                {r.resources.map((res, i) => (
                  <ResourceRow key={i} res={res} testID={`task-resource-${i}`} />
                ))}
                <AiNote />
              </View>
            ) : null}
          </ScrollView>
        </>
      ) : null}
    </Sheet>
  );
}

export function Block({ title, items, numbered, icon }: { title: string; items: string[]; numbered?: boolean; icon?: IconName }) {
  const styles = useTaskSheetStyles();
  const { colors } = useTheme();
  return (
    <View style={{ gap: spacing.sm }}>
      <Txt variant="heading">{title}</Txt>
      {items.map((s, i) => (
        <View key={i} style={{ flexDirection: "row", gap: spacing.md, alignItems: "flex-start" }}>
          {numbered ? (
            <View style={styles.num}>
              <Text style={styles.numText}>{i + 1}</Text>
            </View>
          ) : (
            <Ionicons name={icon!} size={18} color={colors.brandPrimary} style={{ marginTop: 2 }} />
          )}
          <Txt style={{ flex: 1 }}>{s}</Txt>
        </View>
      ))}
    </View>
  );
}

export function ResourceRow({ res, testID }: { res: Resource; testID: string }) {
  const styles = useTaskSheetStyles();
  const { colors } = useTheme();
  const { t } = useAuth();
  return (
    <PressableScale testID={testID} onPress={() => WebBrowser.openBrowserAsync(res.url)} style={styles.res}>
      <View style={styles.resIcon}>
        <Ionicons name={TYPE_ICON[res.type] || "link-outline"} size={22} color={colors.onBrandTertiary} />
      </View>
      <View style={{ flex: 1, gap: 2 }}>
        <Text style={styles.resType}>{t.road.resourceTypes[res.type] || res.platform || t.road.linkFallback}</Text>
        <Text style={styles.resTitle}>{res.title}</Text>
        <Text style={styles.resDesc} numberOfLines={2}>
          {res.description}
        </Text>
      </View>
      <Ionicons name="open-outline" size={18} color={colors.muted} />
    </PressableScale>
  );
}

export function MilestoneSheet({
  milestone,
  index,
  onClose,
  onTask,
}: {
  milestone: Milestone | null;
  index: number;
  onClose: () => void;
  onTask: (t: Task) => void;
}) {
  const styles = useTaskSheetStyles();
  const { colors } = useTheme();
  const { t } = useAuth();
  return (
    <Sheet visible={!!milestone} onClose={onClose} testID="milestone-sheet">
      {milestone ? (
        <>
          <View style={styles.headRow}>
            <View style={{ flex: 1, gap: 4 }}>
              <Text style={styles.kicker}>
                {t.road.positionKicker} · {t.road.levelBadge(index + 1)}
              </Text>
              <Txt variant="title" testID="milestone-sheet-title">
                {milestone.title}
              </Txt>
            </View>
            <IconButton testID="milestone-sheet-close" icon="close" onPress={onClose} />
          </View>
          <ScrollView style={{ flexShrink: 1 }} contentContainerStyle={{ gap: spacing.lg, paddingBottom: spacing.lg }} showsVerticalScrollIndicator={false}>
            <Txt>{milestone.description}</Txt>
            <View style={{ flexDirection: "row", gap: spacing.sm, flexWrap: "wrap" }}>
              {milestone.salary ? (
                <View style={styles.pill}>
                  <Ionicons name="cash-outline" size={16} color={colors.onBrandTertiary} />
                  <Text style={styles.pillText}>{milestone.salary}</Text>
                </View>
              ) : null}
              {milestone.years ? (
                <View style={styles.pill}>
                  <Ionicons name="time-outline" size={16} color={colors.onBrandTertiary} />
                  <Text style={styles.pillText}>{milestone.years}</Text>
                </View>
              ) : null}
            </View>
            {milestone.requirements?.length ? <Block title={t.road.requirementsFromOffers} items={milestone.requirements} icon="clipboard-outline" /> : null}
            <Txt variant="heading">{t.road.tasksToComplete}</Txt>
            {milestone.tasks.map((t2) => (
              <PressableScale key={t2.id} testID={`milestone-task-${t2.id}`} onPress={() => onTask(t2)} style={styles.taskRow}>
                <Ionicons name={t2.done ? "checkmark-circle" : "ellipse-outline"} size={24} color={t2.done ? colors.brandPrimary : colors.borderStrong} />
                <View style={{ flex: 1 }}>
                  <Text style={[styles.resTitle, t2.done && { color: colors.muted, textDecorationLine: "line-through" }]}>{t2.title}</Text>
                  <Text style={styles.resDesc} numberOfLines={2}>
                    {t2.description}
                  </Text>
                </View>
                <Ionicons name="chevron-forward" size={18} color={colors.muted} />
              </PressableScale>
            ))}
            <AiNote />
          </ScrollView>
        </>
      ) : null}
    </Sheet>
  );
}

export const useTaskSheetStyles = makeStyles((c) => ({
  backdrop: { flex: 1, backgroundColor: c.overlay },
  sheet: {
    maxHeight: "88%",
    backgroundColor: c.surface,
    borderTopLeftRadius: radius.lg + 8,
    borderTopRightRadius: radius.lg + 8,
    paddingHorizontal: spacing.xl,
    paddingTop: spacing.sm,
    gap: spacing.md,
  },
  handle: { alignSelf: "center", width: 40, height: 5, borderRadius: 3, backgroundColor: c.borderStrong, marginBottom: spacing.sm },
  headRow: { flexDirection: "row", gap: spacing.md, alignItems: "flex-start" },
  kicker: { fontFamily: fonts.bold, fontSize: 11, letterSpacing: 1, color: c.brandPrimary },
  loading: { flexDirection: "row", gap: spacing.md, alignItems: "center", padding: spacing.lg, backgroundColor: c.surfaceSecondary, borderRadius: radius.lg },
  pill: { flexDirection: "row", alignItems: "center", gap: 6, alignSelf: "flex-start", backgroundColor: c.brandTertiary, borderRadius: radius.pill, paddingHorizontal: spacing.md, paddingVertical: 6 },
  pillText: { fontFamily: fonts.semibold, fontSize: 13, color: c.onBrandTertiary },
  num: { width: 26, height: 26, borderRadius: 13, backgroundColor: c.brandTertiary, alignItems: "center", justifyContent: "center" },
  numText: { fontFamily: fonts.bold, fontSize: 12, color: c.onBrandTertiary },
  res: { flexDirection: "row", gap: spacing.md, alignItems: "center", padding: spacing.md, borderRadius: radius.md, backgroundColor: c.surfaceSecondary, borderWidth: 1, borderColor: c.border },
  resIcon: { width: 44, height: 44, borderRadius: radius.md, backgroundColor: c.brandTertiary, alignItems: "center", justifyContent: "center" },
  resType: { fontFamily: fonts.bold, fontSize: 10, letterSpacing: 0.5, color: c.brandPrimary, textTransform: "uppercase" },
  resTitle: { fontFamily: fonts.bold, fontSize: 15, color: c.onSurface },
  resDesc: { fontFamily: fonts.regular, fontSize: 13, lineHeight: 18, color: c.muted },
  taskRow: { flexDirection: "row", gap: spacing.md, alignItems: "center", padding: spacing.md, borderRadius: radius.md, backgroundColor: c.surfaceSecondary, minHeight: 56 },
}));
