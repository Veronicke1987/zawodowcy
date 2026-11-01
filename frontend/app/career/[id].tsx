import { useQuery } from "@tanstack/react-query";
import * as WebBrowser from "expo-web-browser";
import { LinearGradient } from "expo-linear-gradient";
import { useLocalSearchParams, useRouter } from "expo-router";
import { useEffect, useRef, useState } from "react";
import { ActivityIndicator, Modal, ScrollView, Text, View } from "react-native";
import Animated, { FadeIn, ZoomIn } from "react-native-reanimated";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import Svg, { Circle, Path } from "react-native-svg";

import { useAds } from "@/src/ads/AdsProvider";
import { api, Career, PathsResponse } from "@/src/api";
import { useAuth } from "@/src/auth";
import { Badge, Button, ErrorBox, IconButton, Ionicons, IconName, AiNote, PressableScale, Txt } from "@/src/components/ui";
import { queryClient } from "@/src/query-client";
import { playSuccess } from "@/src/sound";
import { fonts, makeStyles, radius, spacing, useTheme } from "@/src/theme";

// Keyword → icon mapping so every career gets a fitting, consistent flat-icon
// hero (same visual language as the auth screen) instead of a generic stock photo.
const ICON_RULES: [RegExp, IconName][] = [
  [/it\b|program|dane|analiti?k|wdroż|cyfrow|technolog/i, "laptop"],
  [/opiek|zdrow|pielęgn|terapeut|medyczn/i, "heart"],
  [/gastronom|kuch|kelner|piekarz|cukiernik/i, "restaurant"],
  [/elektryk|mechanik|budow|hydraulik|stolarz|spawacz|monter/i, "hammer"],
  [/transport|kierowc|logisty|magazyn|spedyc/i, "car"],
  [/fryzjer|kosmet|uroda|wizaż/i, "cut"],
  [/nauczyciel|edukac|trener|szkolen/i, "school"],
  [/sprzedaż|handel|marketing|reklam/i, "megaphone"],
  [/finans|księgow|bank|podatk/i, "calculator"],
  [/prawn|kancelar/i, "briefcase"],
  [/rolnict|ogrodnict|lesnict|zielen/i, "leaf"],
  [/sztuk|kultur|floryst|projekt.*graficzn/i, "color-palette"],
  [/sport|fitness|trener personal/i, "fitness"],
  [/kadr|hr\b|personal/i, "people"],
];

function careerIcon(career?: Career): IconName {
  const haystack = `${career?.title ?? ""} ${career?.industry ?? ""}`;
  for (const [re, icon] of ICON_RULES) if (re.test(haystack)) return icon;
  return "briefcase";
}

type Detail = {
  description: string;
  daily_tasks: string[];
  pros: string[];
  cons: string[];
  requirements: string[];
  how_to_start: string[];
  career_levels: string[];
};

export default function CareerDetail() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const insets = useSafeAreaInsets();
  const styles = useStyles();
  const { colors } = useTheme();
  const router = useRouter();
  const { refresh, t } = useAuth();
  const [choosing, setChoosing] = useState(false);
  const [celebrate, setCelebrate] = useState(false);
  const [chooseError, setChooseError] = useState("");
  const [limitHit, setLimitHit] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => () => {
    if (timer.current) clearTimeout(timer.current);
  }, []);

  const q = useQuery({
    queryKey: ["career", id],
    queryFn: () => api<{ career: Career; detail: Detail; job_links: { label: string; url: string }[] }>(`/careers/${id}`),
    staleTime: Infinity,
  });

  const choose = async () => {
    if (choosing) return;
    setChooseError("");
    setLimitHit(false);
    const existing = paths.data?.paths.some((p) => p.title === career?.title);
    if (!existing && atLimit) {
      setChooseError(t.career.limitReached);
      setLimitHit(true);
      return;
    }
    // re-activating an existing path generates nothing, so no ad
    if (!existing && !(await watchRoadmapAd(t.ads.reasonBuildPath))) return;
    setChoosing(true);
    try {
      await api("/roadmap", { method: "POST", body: { career_id: id } });
      queryClient.invalidateQueries({ queryKey: ["roadmap"] });
      queryClient.invalidateQueries({ queryKey: ["paths"] });
      refresh();
      setCelebrate(true);
      playSuccess();
      timer.current = setTimeout(() => {
        setCelebrate(false);
        router.dismissTo("/(tabs)/road");
      }, 2200);
    } catch (e: any) {
      setChooseError(e.message);
      setLimitHit(e.status === 403);
    } finally {
      setChoosing(false);
    }
  };

  const career = q.data?.career;
  const d = q.data?.detail;
  const { showAds, watchRoadmapAd } = useAds();
  const paths = useQuery({ queryKey: ["paths", "detail"], queryFn: () => api<PathsResponse>("/paths") });
  const atLimit = (paths.data?.paths.length ?? 0) >= (paths.data?.limit ?? 3);
  const alreadyMine = !!paths.data?.paths.some((p) => p.title === q.data?.career?.title);

  return (
    <View style={styles.root}>
      <ScrollView contentContainerStyle={{ paddingBottom: 120 + insets.bottom }} testID="career-detail-scroll">
        <View style={styles.hero}>
          <LinearGradient colors={[colors.brandPrimary, colors.brandSecondary]} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={StyleFill} />
          <Svg style={StyleFill} viewBox="0 0 390 220" preserveAspectRatio="xMidYMid slice">
            <Circle cx={345} cy={30} r={100} fill={colors.onBrandPrimary} opacity={0.08} />
            <Circle cx={20} cy={200} r={80} fill={colors.onBrandPrimary} opacity={0.07} />
            <Path d="M -10 190 C 90 150, 140 190, 220 140 S 330 90, 400 70" stroke={colors.onBrandPrimary} strokeOpacity={0.3} strokeWidth={3} strokeDasharray="2,10" strokeLinecap="round" fill="none" />
          </Svg>
          <View style={styles.heroBadge} testID="career-hero-icon">
            <Ionicons name={careerIcon(career)} size={46} color={colors.onBrandTertiary} />
          </View>
          <LinearGradient colors={["transparent", colors.surface]} style={[StyleFill, { top: "60%" }]} />
        </View>
        <View style={styles.body}>
          {career ? (
            <>
              <Badge label={career.category === "now" ? t.career.badgeNow : t.career.badgeFuture} />
              <Txt variant="display" testID="career-title">
                {career.title}
              </Txt>
              <View style={styles.metaRow}>
                <Badge label={`${career.match}${t.career.matchSuffix}`} tone="success" />
                {career.salary ? <Badge label={career.salary} tone="neutral" /> : null}
              </View>
              {career.why ? <Txt>{career.why}</Txt> : null}
            </>
          ) : null}

          {q.isLoading ? (
            <View style={styles.loading} testID="career-loading">
              <ActivityIndicator color={colors.brandPrimary} />
              <Txt>{t.career.loadingDetail}</Txt>
            </View>
          ) : q.isError ? (
            <ErrorBox testID="career-error" message={(q.error as Error).message} onRetry={() => q.refetch()} />
          ) : d ? (
            <Animated.View entering={FadeIn.duration(400)} style={{ gap: spacing.xl }}>
              <Section title={t.career.sectionWhatYouDo} icon="document-text-outline">
                <Txt testID="career-description">{d.description}</Txt>
                <List items={d.daily_tasks} icon="ellipse" iconSize={8} color={colors.muted} />
              </Section>
              <View style={styles.proCon}>
                <View style={[styles.pcBox, { backgroundColor: colors.successTint }]} testID="career-pros">
                  <Text style={[styles.pcTitle, { color: colors.success }]}>{t.career.sectionPros}</Text>
                  <List items={d.pros} icon="checkmark-circle" color={colors.success} />
                </View>
                <View style={[styles.pcBox, { backgroundColor: colors.errorTint }]} testID="career-cons">
                  <Text style={[styles.pcTitle, { color: colors.error }]}>{t.career.sectionCons}</Text>
                  <List items={d.cons} icon="close-circle" color={colors.error} />
                </View>
              </View>
              <Section title={t.career.sectionRequirements} icon="clipboard-outline">
                <List items={d.requirements} icon="checkbox-outline" color={colors.brandPrimary} />
              </Section>
              <Section title={t.career.sectionHowToStart} icon="rocket-outline">
                {d.how_to_start.map((s, i) => (
                  <View key={i} style={styles.stepRow}>
                    <View style={styles.stepNum}>
                      <Text style={styles.stepNumText}>{i + 1}</Text>
                    </View>
                    <Txt style={{ flex: 1 }}>{s}</Txt>
                  </View>
                ))}
              </Section>
              {d.career_levels?.length ? (
                <Section title={t.career.sectionCareerLevels} icon="trending-up-outline">
                  <Txt>{d.career_levels.join("  →  ")}</Txt>
                </Section>
              ) : null}
              <Section title={t.career.sectionJobOffers} icon="search-outline">
                <View style={styles.links}>
                  {q.data!.job_links.map((l) => (
                    <PressableScale
                      key={l.label}
                      testID={`job-link-${l.label.replace(/\W/g, "").toLowerCase()}`}
                      onPress={() => WebBrowser.openBrowserAsync(l.url)}
                      style={styles.linkBtn}
                    >
                      <Text style={styles.linkText}>{l.label}</Text>
                      <Ionicons name="open-outline" size={14} color={colors.onSurface} />
                    </PressableScale>
                  ))}
                </View>
              </Section>
            </Animated.View>
          ) : null}
          <AiNote style={{ marginTop: spacing.lg }} />
        </View>
      </ScrollView>

      <View style={[styles.topBar, { top: insets.top + spacing.sm }]}>
        <IconButton testID="career-back-button" icon="arrow-back" onPress={() => (router.canGoBack() ? router.back() : router.replace("/(tabs)"))} />
      </View>

      <View style={[styles.sticky, { paddingBottom: insets.bottom + spacing.md }]}>
        {chooseError ? <ErrorBox testID="choose-error" message={chooseError} /> : null}
        {!limitHit && showAds && !alreadyMine && !atLimit ? (
          <Text style={styles.notice} testID="choose-ad-notice">
            {t.career.adNotice}{" "}
            <Text style={styles.noticeLink} testID="choose-go-premium" onPress={() => router.push("/premium")} suppressHighlighting>
              {t.career.goPremiumInline}
            </Text>
          </Text>
        ) : null}
        {limitHit ? (
          <Button testID="choose-manage-paths" title={t.career.managePaths} variant="ghost" onPress={() => router.dismissTo("/(tabs)/road")} />
        ) : null}
        <Button testID="choose-path-button" title={t.career.chooseButton} icon="flag" onPress={choose} loading={choosing} disabled={!d} />
      </View>

      <Modal visible={celebrate} transparent animationType="fade" statusBarTranslucent>
        <View style={styles.overlay}>
          <Animated.View entering={ZoomIn.springify()} style={styles.celebrate} testID="celebration-modal">
            <View style={styles.celebrateIcon}>
              <Ionicons name="trophy" size={44} color={colors.onBrandPrimary} />
            </View>
            <Txt variant="title" style={{ textAlign: "center" }}>
              {t.career.celebrateTitle}
            </Txt>
            <Txt style={{ textAlign: "center" }}>{t.career.celebrateText(career?.title)}</Txt>
          </Animated.View>
        </View>
      </Modal>
    </View>
  );
}

const StyleFill = { position: "absolute" as const, left: 0, right: 0, top: 0, bottom: 0 };

function Section({ title, icon, children }: { title: string; icon: IconName; children: React.ReactNode }) {
  const { colors } = useTheme();
  return (
    <View style={{ gap: spacing.md }}>
      <View style={{ flexDirection: "row", alignItems: "center", gap: spacing.sm }}>
        <Ionicons name={icon} size={20} color={colors.brandPrimary} />
        <Txt variant="heading">{title}</Txt>
      </View>
      {children}
    </View>
  );
}

function List({ items, icon, color, iconSize = 18 }: { items: string[]; icon: IconName; color: string; iconSize?: number }) {
  return (
    <View style={{ gap: spacing.sm }}>
      {(items || []).map((t, i) => (
        <View key={i} style={{ flexDirection: "row", gap: spacing.sm, alignItems: "flex-start" }}>
          <View style={{ paddingTop: iconSize < 12 ? 7 : 2 }}>
            <Ionicons name={icon} size={iconSize} color={color} />
          </View>
          <Txt style={{ flex: 1 }}>{t}</Txt>
        </View>
      ))}
    </View>
  );
}

const useStyles = makeStyles((c) => ({
  root: { flex: 1, backgroundColor: c.surface },
  hero: { height: 220, overflow: "hidden", alignItems: "center", justifyContent: "center" },
  heroBadge: {
    width: 96,
    height: 96,
    borderRadius: 48,
    backgroundColor: c.surface,
    alignItems: "center",
    justifyContent: "center",
    shadowColor: "#000",
    shadowOpacity: 0.18,
    shadowRadius: 16,
    shadowOffset: { width: 0, height: 8 },
    elevation: 6,
  },
  body: { paddingHorizontal: spacing.xl, gap: spacing.md, marginTop: -spacing.xxl },
  metaRow: { flexDirection: "row", gap: spacing.sm, flexWrap: "wrap" },
  loading: { flexDirection: "row", gap: spacing.md, alignItems: "center", padding: spacing.lg, backgroundColor: c.surfaceSecondary, borderRadius: radius.lg },
  proCon: { gap: spacing.md },
  pcBox: { borderRadius: radius.lg, padding: spacing.lg, gap: spacing.md },
  pcTitle: { fontFamily: fonts.bold, fontSize: 16 },
  stepRow: { flexDirection: "row", gap: spacing.md, alignItems: "flex-start" },
  stepNum: { width: 28, height: 28, borderRadius: 14, backgroundColor: c.brandTertiary, alignItems: "center", justifyContent: "center" },
  stepNumText: { fontFamily: fonts.bold, color: c.onBrandTertiary, fontSize: 13 },
  links: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  linkBtn: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    minHeight: 44,
    paddingHorizontal: spacing.lg,
    borderRadius: radius.pill,
    borderWidth: 1.5,
    borderColor: c.border,
    backgroundColor: c.surfaceSecondary,
  },
  linkText: { fontFamily: fonts.semibold, fontSize: 14, color: c.onSurface },
  topBar: { position: "absolute", left: spacing.lg },
  notice: { fontFamily: fonts.medium, fontSize: 12, lineHeight: 17, color: c.muted, textAlign: "center" },
  noticeLink: { fontFamily: fonts.bold, color: c.brandPrimary },
  sticky: {
    position: "absolute",
    left: 0,
    right: 0,
    bottom: 0,
    paddingHorizontal: spacing.xl,
    paddingTop: spacing.md,
    gap: spacing.sm,
    backgroundColor: c.surface,
    borderTopWidth: 1,
    borderTopColor: c.divider,
  },
  overlay: { flex: 1, backgroundColor: c.overlay, alignItems: "center", justifyContent: "center", padding: spacing.xl },
  celebrate: { backgroundColor: c.surface, borderRadius: radius.lg, padding: spacing.xxl, alignItems: "center", gap: spacing.md, width: "100%" },
  celebrateIcon: { width: 88, height: 88, borderRadius: 44, backgroundColor: c.brandPrimary, alignItems: "center", justifyContent: "center" },
}));
