import { useQuery } from "@tanstack/react-query";
import { useRouter } from "expo-router";
import { useEffect, useState } from "react";
import { FlatList, Pressable, RefreshControl, Text, View } from "react-native";
import Animated, { FadeInDown, useAnimatedStyle, useSharedValue, withRepeat, withTiming } from "react-native-reanimated";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, Career, Recommendations } from "@/src/api";
import { Badge, Button, ErrorBox, Ionicons, AiNote, PressableScale, Txt } from "@/src/components/ui";
import { StreakBadge } from "@/src/components/Streak";
import { usesNativeTabs } from "@/src/navigation";
import { RESET_MODES } from "@/src/quiz-steps";
import { queryClient } from "@/src/query-client";
import { fonts, makeStyles, radius, spacing, useTheme } from "@/src/theme";

export default function Matches() {
  const insets = useSafeAreaInsets();
  const bottomChrome = usesNativeTabs ? insets.bottom : 0;
  const styles = useStyles();
  const { colors } = useTheme();
  const router = useRouter();
  const [tab, setTab] = useState<"now" | "future">("now");

  const q = useQuery({
    queryKey: ["recommendations"],
    queryFn: () => api<Recommendations>("/recommendations"),
    refetchInterval: (query) => (query.state.data?.status === "pending" ? 3000 : false),
  });

  const regenerate = async () => {
    await api("/recommendations/generate", { method: "POST" });
    queryClient.invalidateQueries({ queryKey: ["recommendations"] });
  };

  const data = q.data;
  const list = data?.status === "ready" ? (tab === "now" ? data.now : data.future) || [] : [];

  return (
    <View style={styles.root}>
      <View style={[styles.header, { paddingTop: insets.top + spacing.lg }]}>
        <View style={styles.titleRow}>
          <View style={{ flex: 1, gap: spacing.xs }}>
            <Txt variant="caption" testID="matches-mode">
              {data?.mode && RESET_MODES[data.mode] ? RESET_MODES[data.mode].short : "TWOJE DOPASOWANIA"}
            </Txt>
            <Txt variant="title">Zawody dla Ciebie</Txt>
          </View>
          <StreakBadge testID="matches-streak-badge" />
        </View>
        <View style={styles.segmentRow}>
          <View style={styles.segment}>
            {(
              [
                ["now", "Już teraz", "flash"],
                ["future", "Z nauką", "school"],
              ] as const
            ).map(([k, label, icon]) => (
              <Pressable
                key={k}
                testID={`matches-tab-${k}`}
                onPress={() => setTab(k)}
                style={[styles.segBtn, tab === k && { backgroundColor: colors.surface }]}
              >
                <Ionicons name={icon} size={16} color={tab === k ? colors.brandPrimary : colors.muted} />
                <Text style={[styles.segText, { color: tab === k ? colors.onSurface : colors.muted }]}>{label}</Text>
              </Pressable>
            ))}
          </View>
          <Pressable testID="matches-custom-path-chip" onPress={() => router.push("/custom-path")} style={styles.customChip}>
            <Ionicons name="add-circle-outline" size={18} color={colors.brandPrimary} />
            <Text style={styles.customChipText}>Własny cel</Text>
          </Pressable>
        </View>
      </View>

      {q.isLoading || data?.status === "pending" ? (
        <Analyzing />
      ) : q.isError ? (
        <View style={{ padding: spacing.xl }}>
          <ErrorBox testID="matches-error" message={(q.error as Error).message} onRetry={() => q.refetch()} />
        </View>
      ) : data?.status === "error" ? (
        <View style={{ padding: spacing.xl }}>
          <ErrorBox testID="matches-gen-error" message="Nie udało się przygotować propozycji. Spróbuj ponownie." onRetry={regenerate} />
        </View>
      ) : data?.status === "none" ? (
        <View style={{ padding: spacing.xl, gap: spacing.lg }}>
          <Txt>Nie masz jeszcze propozycji zawodów. Wypełnij krótką ankietę, a AI dobierze zawody dopasowane do Ciebie.</Txt>
          <Button testID="matches-start-quiz" title="Wypełnij ankietę" onPress={() => router.push("/quiz")} />
        </View>
      ) : (
        <FlatList
          testID="matches-list"
          data={list}
          keyExtractor={(i) => i.id}
          contentContainerStyle={{ padding: spacing.xl, paddingTop: spacing.sm, gap: spacing.md, paddingBottom: bottomChrome + spacing.xl }}
          refreshControl={<RefreshControl refreshing={q.isRefetching} onRefresh={() => { q.refetch(); }} tintColor={colors.brandPrimary} />}
          ListHeaderComponent={
            <View style={{ gap: spacing.md, marginBottom: spacing.xs }}>
              {data?.summary && tab === "now" ? (
                <View style={styles.summary} testID="matches-summary">
                  <Ionicons name="sparkles" size={18} color={colors.onBrandTertiary} />
                  <Text style={styles.summaryText}>{data.summary}</Text>
                </View>
              ) : null}
              <Txt variant="caption">
                {tab === "now"
                  ? "Zawody, w których możesz zacząć pracę już teraz"
                  : "Zawody pasujące do Ciebie, które wymagają nowych umiejętności"}
              </Txt>
            </View>
          }
          renderItem={({ item, index }) => <CareerCard career={item} index={index} onPress={() => router.push(`/career/${item.id}`)} />}
          ListEmptyComponent={<Txt>Brak propozycji w tej kategorii.</Txt>}
          ListFooterComponent={list.length ? <AiNote style={{ marginTop: spacing.sm }} /> : null}
        />
      )}
    </View>
  );
}

function CareerCard({ career, index, onPress }: { career: Career; index: number; onPress: () => void }) {
  const styles = useStyles();
  const { colors } = useTheme();
  return (
    <Animated.View entering={FadeInDown.delay(index * 70).duration(400)}>
      <PressableScale testID={`career-card-${index}`} onPress={onPress} style={styles.card}>
        <View style={styles.cardTop}>
          <View style={{ flex: 1, gap: 2 }}>
            <Text style={styles.cardTitle}>{career.title}</Text>
            {career.industry ? <Txt variant="caption">{career.industry}</Txt> : null}
          </View>
          <View style={styles.match}>
            <Text style={styles.matchNum}>{career.match}%</Text>
            <Text style={styles.matchLbl}>dopasowania</Text>
          </View>
        </View>
        <Txt numberOfLines={3}>{career.summary}</Txt>
        <View style={styles.metaRow}>
          {career.salary ? (
            <View style={styles.meta}>
              <Ionicons name="cash-outline" size={14} color={colors.muted} />
              <Text style={styles.metaText}>{career.salary}</Text>
            </View>
          ) : null}
        </View>
        <View style={styles.metaRow}>
          {career.demand ? <Badge label={`Popyt: ${career.demand}`} tone="success" /> : null}
          {career.ai_risk ? <Badge label={`Ryzyko AI: ${career.ai_risk}`} tone="neutral" /> : null}
        </View>
      </PressableScale>
    </Animated.View>
  );
}

function Analyzing() {
  const styles = useStyles();
  const { colors } = useTheme();
  const pulse = useSharedValue(0.4);
  useEffect(() => {
    pulse.value = withRepeat(withTiming(1, { duration: 900 }), -1, true);
  }, [pulse]);
  const s = useAnimatedStyle(() => ({ opacity: pulse.value }));
  return (
    <View style={{ padding: spacing.xl, gap: spacing.md }} testID="matches-analyzing">
      <View style={styles.summary}>
        <Ionicons name="sparkles" size={18} color={colors.onBrandTertiary} />
        <Text style={styles.summaryText}>AI analizuje Twój profil i wymagania z ofert pracy… To może potrwać do minuty.</Text>
      </View>
      {[0, 1, 2].map((i) => (
        <Animated.View key={i} style={[styles.skeleton, s]} />
      ))}
    </View>
  );
}

const useStyles = makeStyles((c) => ({
  root: { flex: 1, backgroundColor: c.surface },
  header: { paddingHorizontal: spacing.xl, paddingBottom: spacing.md, gap: spacing.xs, backgroundColor: c.surface },
  titleRow: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  segmentRow: { flexDirection: "row", alignItems: "center", gap: spacing.sm, marginTop: spacing.md },
  segment: { flex: 1, flexDirection: "row", backgroundColor: c.surfaceTertiary, borderRadius: radius.pill, padding: 4 },
  segBtn: { flex: 1, height: 44, borderRadius: radius.pill, alignItems: "center", justifyContent: "center", flexDirection: "row", gap: 6 },
  segText: { fontFamily: fonts.bold, fontSize: 14 },
  summary: { flexDirection: "row", gap: spacing.sm, backgroundColor: c.brandTertiary, borderRadius: radius.lg, padding: spacing.lg },
  summaryText: { flex: 1, fontFamily: fonts.medium, fontSize: 14, lineHeight: 20, color: c.onBrandTertiary },
  card: {
    backgroundColor: c.surfaceSecondary,
    borderRadius: radius.lg,
    padding: spacing.lg,
    gap: spacing.md,
    borderWidth: 1,
    borderColor: c.border,
  },
  orRow: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  orLine: { flex: 1, height: 1, backgroundColor: c.divider },
  customChip: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    height: 44,
    borderRadius: radius.pill,
    paddingHorizontal: spacing.md,
    borderWidth: 1.5,
    borderColor: c.brandPrimary,
    borderStyle: "dashed",
  },
  customChipText: { fontFamily: fonts.bold, fontSize: 13, color: c.brandPrimary },
  cardTop: { flexDirection: "row", gap: spacing.md, alignItems: "flex-start" },
  cardTitle: { fontFamily: fonts.bold, fontSize: 18, lineHeight: 24, color: c.onSurface },
  match: { backgroundColor: c.brandPrimary, borderRadius: radius.md, paddingHorizontal: 10, paddingVertical: 6, alignItems: "center" },
  matchNum: { fontFamily: fonts.extrabold, fontSize: 18, color: c.onBrandPrimary },
  matchLbl: { fontFamily: fonts.medium, fontSize: 9, color: c.onBrandPrimary },
  metaRow: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  meta: { flexDirection: "row", alignItems: "center", gap: 4 },
  metaText: { fontFamily: fonts.semibold, fontSize: 13, color: c.onSurfaceSecondary },
  skeleton: { height: 150, borderRadius: radius.lg, backgroundColor: c.surfaceTertiary },
}));
