import * as Haptics from "expo-haptics";
import { useLocalSearchParams, useRouter } from "expo-router";
import { useEffect, useMemo, useState } from "react";
import { ActivityIndicator, Pressable, Text, TextInput, View } from "react-native";
import { KeyboardAwareScrollView, KeyboardStickyView } from "react-native-keyboard-controller";
import Animated, { FadeInRight, useAnimatedStyle, withTiming } from "react-native-reanimated";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api } from "@/src/api";
import { useAds } from "@/src/ads/AdsProvider";
import { useAuth } from "@/src/auth";
import { Button, Chip, ErrorBox, IconButton, IconName, Ionicons, Txt } from "@/src/components/ui";
import { queryClient } from "@/src/query-client";
import { Group, QUIZ_STEPS } from "@/src/quiz-steps";
import { fonts, makeStyles, radius, spacing, useTheme } from "@/src/theme";

type Answers = Record<string, any>;

export default function Quiz() {
  const insets = useSafeAreaInsets();
  const styles = useStyles();
  const { colors } = useTheme();
  const router = useRouter();
  const { edit } = useLocalSearchParams<{ edit?: string }>();
  const { refresh } = useAuth();
  const { watchAd, showAds } = useAds();  const [step, setStep] = useState(0);
  const [answers, setAnswers] = useState<Answers>({ personality: {} });
  const [loadingPrev, setLoadingPrev] = useState(!!edit);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!edit) return;
    api<{ answers: Answers | null }>("/profile")
      .then((p) => p.answers && setAnswers({ personality: {}, ...p.answers }))
      .catch(() => {})
      .finally(() => setLoadingPrev(false));
  }, [edit]);

  const steps = useMemo(() => QUIZ_STEPS.filter((s) => !s.showIf || s.showIf(answers)), [answers]);
  const current = steps[Math.min(step, steps.length - 1)];
  const isLast = step >= steps.length - 1;
  const canNext = current.groups.every((g) => {
    if (!g.required) return true;
    const v = answers[g.key];
    return Array.isArray(v) ? v.length > 0 : !!v;
  });

  const progressStyle = useAnimatedStyle(() => ({
    width: withTiming(`${((step + 1) / steps.length) * 100}%`, { duration: 300 }),
  }));

  const set = (key: string, value: any) => setAnswers((a) => ({ ...a, [key]: value }));

  const next = async () => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light).catch(() => {});
    if (!isLast) return setStep(step + 1);
    // re-editing an existing profile generates new AI proposals, so it's ad-gated
    // like other AI-generation actions; the very first onboarding quiz is not.
    if (edit && !(await watchAd("otrzymać nowe propozycje zawodów"))) return;
    setSaving(true);
    setError("");
    try {
      // send only answers from steps visible in the chosen mode
      const keys = new Set(["personality", ...steps.flatMap((s) => s.groups.map((g) => g.key))]);
      const clean = Object.fromEntries(Object.entries(answers).filter(([k]) => keys.has(k)));
      await api("/profile", { method: "PUT", body: { answers: clean } });
      await api("/recommendations/generate", { method: "POST" });
      queryClient.invalidateQueries({ queryKey: ["recommendations"] });
      await refresh();
      if (edit) router.dismissTo("/(tabs)");
      else router.replace("/(tabs)");
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  };

  const back = () => {
    if (step > 0) setStep(step - 1);
    else if (router.canGoBack()) router.back();
  };

  if (loadingPrev) {
    return (
      <View style={[styles.root, { alignItems: "center", justifyContent: "center" }]}>
        <ActivityIndicator color={colors.brandPrimary} />
      </View>
    );
  }

  return (
    <View style={styles.root}>
      <View style={[styles.header, { paddingTop: insets.top + spacing.sm }]}>
        <View style={styles.headerRow}>
          {step > 0 || router.canGoBack() ? <IconButton testID="quiz-back-button" icon="arrow-back" onPress={back} /> : <View style={{ width: 44 }} />}
          <Text style={styles.stepText} testID="quiz-step-indicator">
            Pytanie {step + 1} z {steps.length}
          </Text>
          <View style={{ width: 44 }} />
        </View>
        <View style={styles.track}>
          <Animated.View style={[styles.bar, progressStyle]} />
        </View>
      </View>

      <KeyboardAwareScrollView
        bottomOffset={110}
        keyboardShouldPersistTaps="handled"
        contentContainerStyle={{ padding: spacing.xl, paddingBottom: 140 + insets.bottom }}
      >
        <Animated.View key={step} entering={FadeInRight.duration(280)} style={{ gap: spacing.xl }}>
          <View style={{ gap: spacing.sm }}>
            <Txt variant="display" testID="quiz-question-title">
              {current.title}
            </Txt>
            <Txt>{current.subtitle}</Txt>
          </View>
          {current.groups.map((g) => (
            <GroupInput key={g.key} group={g} value={answers[g.key]} onChange={(v) => set(g.key, v)} />
          ))}
          {error ? <ErrorBox testID="quiz-error" message={error} /> : null}
        </Animated.View>
      </KeyboardAwareScrollView>

      <KeyboardStickyView offset={{ opened: insets.bottom }} style={styles.sticky}>
        <View style={[styles.stickyInner, { paddingBottom: insets.bottom + spacing.md }]}>
          {edit && isLast && showAds ? (
            <Text style={styles.notice} testID="quiz-ad-notice">
              Przed nowymi propozycjami zobaczysz krótką reklamę.
            </Text>
          ) : null}
          <Button
            testID="quiz-next-button"
            title={isLast ? "Pokaż moje zawody" : "Dalej"}
            icon={isLast ? "sparkles" : "arrow-forward"}
            disabled={!canNext}
            loading={saving}
            onPress={next}
          />
        </View>
      </KeyboardStickyView>
    </View>
  );
}

function GroupInput({ group, value, onChange }: { group: Group; value: any; onChange: (v: any) => void }) {
  const styles = useStyles();
  const { colors } = useTheme();
  return (
    <View style={{ gap: spacing.md }}>
      {group.label ? <Txt variant="label">{group.label}</Txt> : null}
      {group.type === "cards"
        ? group.cards!.map((c) => {
            const selected = value === c.value;
            return (
              <Pressable
                key={c.value}
                testID={`quiz-mode-${c.value}`}
                onPress={() => {
                  Haptics.selectionAsync().catch(() => {});
                  onChange(c.value);
                }}
                style={[styles.modeCard, selected && { borderColor: colors.brandPrimary, backgroundColor: colors.brandTertiary }]}
              >
                <View style={[styles.modeIcon, { backgroundColor: selected ? colors.brandPrimary : colors.surfaceTertiary }]}>
                  <Ionicons name={c.icon as IconName} size={24} color={selected ? colors.onBrandPrimary : colors.onSurface} />
                </View>
                <View style={{ flex: 1, gap: 2 }}>
                  <Text style={[styles.modeTitle, selected && { color: colors.onBrandTertiary }]}>{c.label}</Text>
                  <Txt variant="caption" style={{ fontSize: 13, lineHeight: 18 }}>
                    {c.desc}
                  </Txt>
                </View>
                <Ionicons name={selected ? "radio-button-on" : "radio-button-off"} size={22} color={selected ? colors.brandPrimary : colors.borderStrong} />
              </Pressable>
            );
          })
        : null}
      {group.type === "single" || group.type === "multi" ? (
        <View style={styles.chips}>
          {group.options!.map((o, i) => {
            const selected = group.type === "single" ? value === o : (value || []).includes(o);
            return (
              <Chip
                key={o}
                testID={`quiz-option-${group.key}-${i}`}
                label={o}
                selected={selected}
                onPress={() => {
                  if (group.type === "single") onChange(o);
                  else onChange(selected ? value.filter((x: string) => x !== o) : [...(value || []), o]);
                }}
              />
            );
          })}
        </View>
      ) : null}
      {group.type === "text" ? (
        <TextInput
          testID={`quiz-input-${group.key}`}
          value={value || ""}
          onChangeText={onChange}
          placeholder={group.placeholder}
          placeholderTextColor={colors.muted}
          multiline={group.multiline}
          style={[styles.input, group.multiline && { minHeight: 120, textAlignVertical: "top", paddingTop: spacing.md }]}
        />
      ) : null}
      {group.type === "traits"
        ? group.traits!.map((t) => (
            <Spectrum
              key={t.key}
              testID={`quiz-trait-${t.key}`}
              left={t.left}
              right={t.right}
              value={(value || {})[t.key] ?? 3}
              onChange={(v) => onChange({ ...(value || {}), [t.key]: v })}
            />
          ))
        : null}
    </View>
  );
}

function Spectrum({ left, right, value, onChange, testID }: { left: string; right: string; value: number; onChange: (v: number) => void; testID: string }) {
  const styles = useStyles();
  const { colors } = useTheme();
  return (
    <View style={styles.spectrum} testID={testID}>
      <View style={styles.specLabels}>
        <Text style={[styles.specLabel, value < 3 && { color: colors.onSurface }]}>{left}</Text>
        <Text style={[styles.specLabel, { textAlign: "right" }, value > 3 && { color: colors.onSurface }]}>{right}</Text>
      </View>
      <View style={styles.specRow}>
        <View style={styles.specLine} />
        {[1, 2, 3, 4, 5].map((n) => (
          <Pressable
            key={n}
            testID={`${testID}-${n}`}
            hitSlop={8}
            onPress={() => {
              Haptics.selectionAsync().catch(() => {});
              onChange(n);
            }}
            style={styles.specHit}
          >
            <View
              style={[
                styles.dot,
                n === value
                  ? { width: 28, height: 28, backgroundColor: colors.brandPrimary, borderColor: colors.brandPrimary }
                  : { backgroundColor: colors.surface },
              ]}
            />
          </Pressable>
        ))}
      </View>
    </View>
  );
}

const useStyles = makeStyles((c) => ({
  root: { flex: 1, backgroundColor: c.surface },
  header: { paddingHorizontal: spacing.xl, gap: spacing.md, paddingBottom: spacing.md, backgroundColor: c.surface },
  headerRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  stepText: { fontFamily: fonts.semibold, fontSize: 14, color: c.muted },
  track: { height: 8, borderRadius: radius.pill, backgroundColor: c.surfaceTertiary, overflow: "hidden" },
  bar: { height: 8, borderRadius: radius.pill, backgroundColor: c.brandPrimary },
  chips: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  modeCard: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    padding: spacing.lg,
    borderRadius: radius.lg,
    borderWidth: 2,
    borderColor: c.border,
    backgroundColor: c.surfaceSecondary,
  },
  modeIcon: { width: 48, height: 48, borderRadius: radius.md, alignItems: "center", justifyContent: "center" },
  modeTitle: { fontFamily: fonts.bold, fontSize: 16, color: c.onSurface },
  input: {
    minHeight: 52,
    borderRadius: radius.md,
    backgroundColor: c.surfaceSecondary,
    borderWidth: 1,
    borderColor: c.border,
    paddingHorizontal: spacing.lg,
    fontFamily: fonts.medium,
    fontSize: 15,
    color: c.onSurface,
  },
  sticky: { position: "absolute", left: 0, right: 0, bottom: 0 },
  stickyInner: { paddingHorizontal: spacing.xl, paddingTop: spacing.md, backgroundColor: c.surface, borderTopWidth: 1, borderTopColor: c.divider, gap: spacing.sm },
  notice: { fontFamily: fonts.medium, fontSize: 12, lineHeight: 17, color: c.muted, textAlign: "center" },
  spectrum: { backgroundColor: c.surfaceSecondary, borderRadius: radius.lg, padding: spacing.lg, gap: spacing.md },
  specLabels: { flexDirection: "row", justifyContent: "space-between", gap: spacing.md },
  specLabel: { flex: 1, fontFamily: fonts.semibold, fontSize: 13, color: c.muted },
  specRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", height: 44 },
  specLine: { position: "absolute", left: 22, right: 22, height: 3, borderRadius: 2, backgroundColor: c.surfaceTertiary },
  specHit: { width: 44, height: 44, alignItems: "center", justifyContent: "center" },
  dot: { width: 18, height: 18, borderRadius: 14, borderWidth: 2, borderColor: c.borderStrong },
}));
