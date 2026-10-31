import { useQuery } from "@tanstack/react-query";
import { useRouter } from "expo-router";
import { useEffect, useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, Text, TextInput, View } from "react-native";
import Animated, { FadeInDown } from "react-native-reanimated";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { useAds } from "@/src/ads/AdsProvider";
import { api, DailyItem, DailyPlan, StudyPlan, TaskResources } from "@/src/api";
import { Badge, Button, Chip, ErrorBox, IconButton, Ionicons, PressableScale, Txt } from "@/src/components/ui";
import { Block, ResourceRow, Sheet, useTaskSheetStyles } from "@/src/components/TaskSheet";
import { queryClient } from "@/src/query-client";
import { playSuccess } from "@/src/sound";
import { fonts, makeStyles, radius, spacing, useTheme } from "@/src/theme";

const WEEKDAY_LABELS = ["Pon", "Wt", "Śr", "Czw", "Pt", "Sob", "Nd"];
const WEEKDAY_FULL = ["poniedziałek", "wtorek", "środa", "czwartek", "piątek", "sobota", "niedziela"];

function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

export default function PlanScreen() {
  const insets = useSafeAreaInsets();
  const styles = useStyles();
  const router = useRouter();
  const [tab, setTab] = useState<"daily" | "weekly">("daily");

  return (
    <View style={styles.root}>
      <View style={[styles.header, { paddingTop: insets.top + spacing.sm }]}>
        <IconButton testID="plan-back-button" icon="arrow-back" onPress={() => (router.canGoBack() ? router.back() : router.replace("/(tabs)/road"))} />
        <View style={{ flex: 1 }}>
          <Txt variant="heading">Plan nauki</Txt>
        </View>
      </View>

      <View style={styles.tabs} testID="plan-tabs">
        <Pressable testID="plan-tab-daily" onPress={() => setTab("daily")} style={[styles.tab, tab === "daily" && styles.tabActive]}>
          <Text style={[styles.tabText, tab === "daily" && styles.tabTextActive]}>Plan dzienny</Text>
        </Pressable>
        <Pressable testID="plan-tab-weekly" onPress={() => setTab("weekly")} style={[styles.tab, tab === "weekly" && styles.tabActive]}>
          <Text style={[styles.tabText, tab === "weekly" && styles.tabTextActive]}>Plan tygodniowy</Text>
        </Pressable>
      </View>

      {tab === "daily" ? <DailyPlanTab /> : <WeeklyPlanTab />}
    </View>
  );
}

// ------------------------------------------------------------------ daily plan (free + premium)
function DailyPlanTab() {
  const insets = useSafeAreaInsets();
  const styles = useStyles();
  const { colors } = useTheme();
  const { watchAd } = useAds();
  const q = useQuery({
    queryKey: ["daily-plan"],
    queryFn: () => api<DailyPlan>("/roadmap/daily-plan"),
    refetchInterval: (query) => (["pending"].includes(query.state.data?.status ?? "") || query.state.data?.next_status === "pending" ? 3000 : false),
  });
  const data = q.data;

  const [editMode, setEditMode] = useState(false);
  const [mode, setMode] = useState<"daily" | "weekly">("daily");
  const [value, setValue] = useState("30");
  const [freeDays, setFreeDays] = useState<number[]>([5, 6]);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState("");
  const [weekIndex, setWeekIndex] = useState<number | null>(null);
  const [unlocking, setUnlocking] = useState(false);
  const [generatingNext, setGeneratingNext] = useState(false);
  const [activeItem, setActiveItem] = useState<DailyItem | null>(null);

  useEffect(() => {
    if (data?.settings) {
      setMode(data.settings.time_mode);
      setValue(String(data.settings.time_value));
      setFreeDays(data.settings.free_days);
    }
  }, [data?.settings]);

  useEffect(() => {
    if (data?.weeks?.length) setWeekIndex((cur) => (cur === null ? data.weeks![data.weeks!.length - 1].index : cur));
  }, [data?.weeks?.length]);

  const toggleFreeDay = (d: number) => setFreeDays((prev) => (prev.includes(d) ? prev.filter((x) => x !== d) : [...prev, d].sort((a, b) => a - b)));

  const submit = async () => {
    setError("");
    const n = parseInt(value, 10);
    if (!n || n <= 0) return setError("Podaj liczbę większą od zera.");
    if (freeDays.length >= 7) return setError("Zostaw przynajmniej jeden dzień nauki w tygodniu.");
    setStarting(true);
    try {
      await api("/roadmap/daily-plan/settings", { method: "POST", body: { time_mode: mode, time_value: n, free_days: freeDays } });
      setEditMode(false);
      setWeekIndex(null);
      queryClient.invalidateQueries({ queryKey: ["daily-plan"] });
    } catch (e: any) {
      setError(e.message);
    } finally {
      setStarting(false);
    }
  };

  const toggleItem = async (item: DailyItem) => {
    const next = !item.done;
    const prev = queryClient.getQueryData<DailyPlan>(["daily-plan"]);
    if (!prev?.weeks) return;
    const updated: DailyPlan = {
      ...prev,
      weeks: prev.weeks.map((w) => ({ ...w, days: w.days.map((d) => ({ ...d, items: d.items.map((it) => (it.id === item.id ? { ...it, done: next } : it)) })) })),
    };
    queryClient.setQueryData(["daily-plan"], updated);
    if (next) playSuccess();
    try {
      await api(`/roadmap/daily-plan/items/${item.id}`, { method: "PATCH", body: { done: next } });
    } catch {
      queryClient.setQueryData(["daily-plan"], prev);
    }
  };

  const unlockWeek = async (index: number) => {
    setUnlocking(true);
    try {
      if (!(await watchAd("zobaczyć resztę tego tygodnia"))) return;
      await api(`/roadmap/daily-plan/weeks/${index}/unlock`, { method: "POST" });
      queryClient.invalidateQueries({ queryKey: ["daily-plan"] });
    } catch (e: any) {
      setError(e.message);
    } finally {
      setUnlocking(false);
    }
  };

  const generateNextWeek = async () => {
    setError("");
    setGeneratingNext(true);
    try {
      await api("/roadmap/daily-plan/next-week", { method: "POST" });
      queryClient.invalidateQueries({ queryKey: ["daily-plan"] });
    } catch (e: any) {
      setError(e.message);
    } finally {
      setGeneratingNext(false);
    }
  };

  if (q.isLoading) {
    return <ActivityIndicator style={{ marginTop: spacing.xxl }} color={colors.brandPrimary} />;
  }
  if (q.isError) {
    return (
      <View style={{ padding: spacing.xl }}>
        <ErrorBox testID="daily-plan-error" message={(q.error as Error).message} onRetry={() => q.refetch()} />
      </View>
    );
  }

  const showForm = editMode || !data || data.status === "none" || data.status === "error";

  if (showForm) {
    return (
      <ScrollView contentContainerStyle={{ padding: spacing.xl, gap: spacing.lg, paddingBottom: insets.bottom + spacing.xl }}>
        {data?.status === "error" ? <ErrorBox testID="daily-plan-gen-error" message="Nie udało się ułożyć planu. Spróbuj ponownie." /> : null}
        <View style={styles.center}>
          <Ionicons name="today-outline" size={44} color={colors.brandPrimary} />
          <Txt variant="title" style={{ textAlign: "center" }}>
            {data?.status === "ready" ? "Zmień ustawienia planu" : "Ułóż plan dzienny"}
          </Txt>
          <Txt style={{ textAlign: "center" }}>Codzienne, konkretne kroki na Twojej drodze kariery.</Txt>
        </View>

        <View style={{ gap: spacing.sm }}>
          <Txt variant="heading">Ile czasu możesz poświęcić?</Txt>
          <View style={{ flexDirection: "row", gap: spacing.sm }}>
            <Chip testID="daily-mode-daily" label="Dziennie" selected={mode === "daily"} onPress={() => setMode("daily")} />
            <Chip testID="daily-mode-weekly" label="Tygodniowo" selected={mode === "weekly"} onPress={() => setMode("weekly")} />
          </View>
          <View style={styles.timeRow}>
            <TextInput testID="daily-time-input" value={value} onChangeText={setValue} keyboardType="number-pad" style={styles.timeInput} maxLength={3} />
            <Txt>{mode === "daily" ? "minut dziennie" : "godzin tygodniowo"}</Txt>
          </View>
        </View>

        <View style={{ gap: spacing.sm }}>
          <Txt variant="heading">Które dni mają być wolne (bez planu)?</Txt>
          <View style={{ flexDirection: "row", gap: spacing.sm, flexWrap: "wrap" }}>
            {WEEKDAY_LABELS.map((label, i) => (
              <Chip key={i} testID={`daily-freeday-${i}`} label={label} selected={freeDays.includes(i)} onPress={() => toggleFreeDay(i)} />
            ))}
          </View>
        </View>

        {!data?.is_premium ? (
          <Txt variant="caption" testID="daily-plan-free-note">
            Jako darmowy użytkownik widzisz od razu 2 najbliższe dni nauki w tygodniu — resztę tygodnia odblokujesz, oglądając reklamę. Premium pokazuje
            od razu cały tydzień.
          </Txt>
        ) : null}

        {error ? <ErrorBox testID="daily-plan-form-error" message={error} /> : null}
        <Button testID="daily-plan-create-button" title={data?.status === "ready" ? "Zapisz i ułóż ten tydzień od nowa" : "Ułóż mój plan dzienny"} icon="sparkles" onPress={submit} loading={starting} />
        {data?.status === "ready" ? (
          <Button testID="daily-plan-cancel-edit" title="Anuluj" variant="ghost" onPress={() => setEditMode(false)} />
        ) : null}
      </ScrollView>
    );
  }

  if (data!.status === "pending") {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color={colors.brandPrimary} />
        <Txt variant="heading">Układam Twój plan dzienny…</Txt>
        <Txt style={{ textAlign: "center" }}>To potrwa około minuty.</Txt>
      </View>
    );
  }

  const weeks = data!.weeks || [];
  const week = weeks.find((w) => w.index === weekIndex) || weeks[weeks.length - 1];
  const isLastWeek = week?.index === weeks[weeks.length - 1]?.index;
  const activeItems = (week?.days || []).filter((d) => !d.free && !d.locked).flatMap((d) => d.items);
  const doneCount = activeItems.filter((it) => it.done).length;
  const lockedDay = (week?.days || []).find((d) => d.locked);
  const today = todayIso();

  return (
    <ScrollView contentContainerStyle={{ padding: spacing.xl, gap: spacing.md, paddingBottom: insets.bottom + spacing.xl }} testID="daily-plan-ready">
      {weeks.length > 1 ? (
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: spacing.sm }} testID="daily-week-switcher">
          {weeks.map((w) => (
            <Chip key={w.index} testID={`daily-week-chip-${w.index}`} label={`Tydzień ${w.index + 1}`} selected={w.index === week?.index} onPress={() => setWeekIndex(w.index)} />
          ))}
        </ScrollView>
      ) : null}

      <View style={styles.summary}>
        <Badge label={`${doneCount}/${activeItems.length || 0} punktów w tym tygodniu`} />
        <Txt variant="caption">
          {data!.settings?.time_mode === "daily" ? `${data!.settings?.time_value} min dziennie` : `${data!.settings?.time_value} h tygodniowo`}
        </Txt>
      </View>

      {(week?.days || []).map((d) => {
        const isToday = d.date === today;
        return (
          <Animated.View key={d.date} entering={FadeInDown} style={[styles.day, isToday && styles.dayToday]} testID={`daily-day-${d.weekday}`}>
            <View style={styles.dayHead}>
              <Text style={[styles.dayName, isToday && { color: colors.brandPrimary }]}>
                {WEEKDAY_FULL[d.weekday].toUpperCase()}
                {isToday ? " · DZIŚ" : ""}
              </Text>
              <Text style={styles.dayDate}>
                {d.date.slice(8, 10)}.{d.date.slice(5, 7)}
              </Text>
            </View>
            {d.free ? (
              <View style={styles.freeRow}>
                <Ionicons name="cafe-outline" size={16} color={colors.muted} />
                <Txt variant="caption">Dzień wolny</Txt>
              </View>
            ) : d.locked ? (
              <View style={styles.freeRow} testID={`daily-day-locked-${d.weekday}`}>
                <Ionicons name="lock-closed" size={16} color={colors.muted} />
                <Txt variant="caption">Zablokowane · {d.locked_count} punkt(y) do odblokowania</Txt>
              </View>
            ) : d.items.length === 0 ? (
              <Txt variant="caption">Brak punktów na ten dzień.</Txt>
            ) : (
              d.items.map((it) => (
                <View key={it.id} style={styles.item}>
                  <Pressable onPress={() => toggleItem(it)} hitSlop={8}>
                    <Ionicons name={it.done ? "checkmark-circle" : "ellipse-outline"} size={22} color={it.done ? colors.brandPrimary : colors.borderStrong} />
                  </Pressable>
                  <PressableScale testID={`daily-item-${it.id}`} onPress={() => setActiveItem(it)} style={{ flex: 1, flexDirection: "row", gap: spacing.sm, alignItems: "flex-start" }}>
                    <View style={{ flex: 1 }}>
                      <Text style={[styles.itemTitle, it.done && { color: colors.muted, textDecorationLine: "line-through" }]}>{it.title}</Text>
                      <Txt variant="caption">{it.description}</Txt>
                    </View>
                    {it.long_term ? <Badge label="co tydzień" tone="neutral" /> : null}
                    <Ionicons name="chevron-forward" size={16} color={colors.muted} />
                  </PressableScale>
                </View>
              ))
            )}
          </Animated.View>
        );
      })}

      {lockedDay ? (
        <Button testID="daily-unlock-week-button" title="Odblokuj resztę tygodnia za reklamę" icon="play-circle" variant="secondary" onPress={() => unlockWeek(week!.index)} loading={unlocking} />
      ) : null}

      {isLastWeek ? (
        data!.next_status === "pending" ? (
          <View style={styles.center} testID="daily-next-week-pending">
            <ActivityIndicator color={colors.brandPrimary} />
            <Txt variant="caption">Generowanie kolejnego tygodnia…</Txt>
          </View>
        ) : data!.can_generate_next ? (
          <Button testID="daily-next-week-button" title="Wygeneruj kolejny tydzień" icon="arrow-forward-circle" onPress={generateNextWeek} loading={generatingNext} />
        ) : (
          <Txt variant="caption" style={{ textAlign: "center" }} testID="daily-next-week-locked">
            Kolejny tydzień odblokuje się w sobotę bieżącego tygodnia.
          </Txt>
        )
      ) : null}

      {error ? <ErrorBox testID="daily-plan-action-error" message={error} /> : null}
      <Button testID="daily-plan-settings-button" title="Zmień ustawienia" variant="ghost" icon="settings-outline" onPress={() => setEditMode(true)} />

      <DailyItemSheet item={activeItem} onClose={() => setActiveItem(null)} />
    </ScrollView>
  );
}

function DailyItemSheet({ item, onClose }: { item: DailyItem | null; onClose: () => void }) {
  const styles = useTaskSheetStyles();
  const { colors } = useTheme();
  const q = useQuery({
    queryKey: ["daily-item-resources", item?.id],
    queryFn: () => api<TaskResources>(`/roadmap/daily-plan/items/${item!.id}/resources`),
    enabled: !!item,
  });
  const data = q.data;

  return (
    <Sheet visible={!!item} onClose={onClose} testID="daily-item-sheet">
      {item ? (
        <View style={{ gap: spacing.lg }}>
          <View style={styles.headRow}>
            <View style={{ flex: 1 }}>
              <Txt variant="heading">{item.title}</Txt>
              <Txt variant="caption" style={{ marginTop: 2 }}>
                {item.description}
              </Txt>
            </View>
          </View>
          {q.isLoading ? (
            <ActivityIndicator style={styles.loading} color={colors.brandPrimary} />
          ) : q.isError ? (
            <ErrorBox testID="daily-item-resources-error" message={(q.error as Error).message} onRetry={() => q.refetch()} />
          ) : data ? (
            <>
              <Txt>{data.overview}</Txt>
              <Block title="Kroki" items={data.steps} numbered icon="checkmark-circle-outline" />
              {data.free_tips?.length ? <Block title="Za darmo" items={data.free_tips} icon="gift-outline" /> : null}
              {data.resources?.length ? (
                <View style={{ gap: spacing.sm }}>
                  <Txt variant="heading">Materiały</Txt>
                  {data.resources.map((r, i) => (
                    <ResourceRow key={i} res={r} testID={`daily-item-resource-${i}`} />
                  ))}
                </View>
              ) : null}
            </>
          ) : null}
        </View>
      ) : null}
    </Sheet>
  );
}

// ------------------------------------------------------------------ weekly study plan (8 weeks, Premium)
function WeeklyPlanTab() {
  const insets = useSafeAreaInsets();
  const styles = useStyles();
  const router = useRouter();
  const { colors } = useTheme();
  const [open, setOpen] = useState<number>(1);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState("");

  const q = useQuery({
    queryKey: ["study-plan"],
    queryFn: () => api<StudyPlan>("/roadmap/study-plan"),
    refetchInterval: (query) => (query.state.data?.status === "pending" ? 3000 : false),
  });

  const create = async () => {
    setError("");
    setStarting(true);
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

  if (!q.isLoading && !data?.is_premium) {
    return (
      <ScrollView contentContainerStyle={{ padding: spacing.xl, paddingBottom: insets.bottom + spacing.xl }}>
        <View style={styles.upsell} testID="plan-weekly-upsell">
          <Ionicons name="diamond" size={40} color={colors.brandPrimary} />
          <Txt variant="title" style={{ textAlign: "center" }}>
            Plan tygodniowy to funkcja Premium
          </Txt>
          <Txt style={{ textAlign: "center" }}>
            Pełny 8-tygodniowy plan nauki z rozpisanymi godzinami dostępny jest w Premium — bez reklam, od razu.
          </Txt>
          <Button testID="plan-weekly-go-premium" title="Przejdź na Premium" icon="diamond" onPress={() => router.push("/premium")} />
        </View>
      </ScrollView>
    );
  }

  return (
    <ScrollView contentContainerStyle={{ padding: spacing.xl, gap: spacing.lg, paddingBottom: insets.bottom + spacing.xl }}>
      {q.isLoading ? (
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
  );
}

const useStyles = makeStyles((c) => ({
  root: { flex: 1, backgroundColor: c.surface },
  header: { flexDirection: "row", alignItems: "center", gap: spacing.md, paddingHorizontal: spacing.lg, paddingBottom: spacing.md, borderBottomWidth: 1, borderBottomColor: c.divider },
  tabs: { flexDirection: "row", gap: spacing.sm, paddingHorizontal: spacing.lg, paddingVertical: spacing.md, borderBottomWidth: 1, borderBottomColor: c.divider },
  tab: { flex: 1, paddingVertical: spacing.sm, borderRadius: radius.pill, alignItems: "center", backgroundColor: c.surfaceSecondary },
  tabActive: { backgroundColor: c.brandPrimary },
  tabText: { fontFamily: fonts.bold, fontSize: 13, color: c.onSurface },
  tabTextActive: { color: c.onBrandPrimary },
  upsell: { alignItems: "center", gap: spacing.md, padding: spacing.xl, borderRadius: radius.lg, backgroundColor: c.brandTertiary },
  center: { alignItems: "center", gap: spacing.md, paddingVertical: spacing.xxl, paddingHorizontal: spacing.xl },
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
  timeRow: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  timeInput: {
    width: 90,
    height: 48,
    borderRadius: radius.md,
    borderWidth: 1.5,
    borderColor: c.border,
    paddingHorizontal: spacing.md,
    fontFamily: fonts.bold,
    fontSize: 16,
    color: c.onSurface,
    backgroundColor: c.surfaceSecondary,
  },
  day: { padding: spacing.lg, borderRadius: radius.lg, backgroundColor: c.surfaceSecondary, borderWidth: 1, borderColor: c.border, gap: spacing.sm },
  dayToday: { borderColor: c.brandPrimary, borderWidth: 2 },
  dayHead: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  dayName: { fontFamily: fonts.bold, fontSize: 12, letterSpacing: 0.5, color: c.onSurface },
  dayDate: { fontFamily: fonts.semibold, fontSize: 12, color: c.muted },
  freeRow: { flexDirection: "row", alignItems: "center", gap: spacing.xs },
}));
