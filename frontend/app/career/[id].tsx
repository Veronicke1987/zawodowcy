import { useQuery } from "@tanstack/react-query";
import * as WebBrowser from "expo-web-browser";
import { Image } from "expo-image";
import { LinearGradient } from "expo-linear-gradient";
import { useLocalSearchParams, useRouter } from "expo-router";
import { useEffect, useRef, useState } from "react";
import { ActivityIndicator, Modal, ScrollView, Text, View } from "react-native";
import Animated, { FadeIn, ZoomIn } from "react-native-reanimated";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, Career } from "@/src/api";
import { Badge, Button, ErrorBox, IconButton, Ionicons, IconName, PressableScale, Txt } from "@/src/components/ui";
import { queryClient } from "@/src/query-client";
import { playSuccess } from "@/src/sound";
import { fonts, makeStyles, radius, spacing, useTheme } from "@/src/theme";

const HERO =
  "https://images.unsplash.com/photo-1510519138101-570d1dca3d66?crop=entropy&cs=srgb&fm=jpg&ixlib=rb-4.1.0&q=85&w=1200";

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
  const [choosing, setChoosing] = useState(false);
  const [celebrate, setCelebrate] = useState(false);
  const [chooseError, setChooseError] = useState("");
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
    setChoosing(true);
    setChooseError("");
    try {
      await api("/roadmap", { method: "POST", body: { career_id: id } });
      queryClient.invalidateQueries({ queryKey: ["roadmap"] });
      setCelebrate(true);
      playSuccess();
      timer.current = setTimeout(() => {
        setCelebrate(false);
        router.dismissTo("/(tabs)/road");
      }, 2200);
    } catch (e: any) {
      setChooseError(e.message);
    } finally {
      setChoosing(false);
    }
  };

  const career = q.data?.career;
  const d = q.data?.detail;

  return (
    <View style={styles.root}>
      <ScrollView contentContainerStyle={{ paddingBottom: 120 + insets.bottom }} testID="career-detail-scroll">
        <View style={styles.hero}>
          <Image source={{ uri: HERO }} style={{ flex: 1 }} contentFit="cover" transition={300} />
          <LinearGradient colors={["rgba(0,0,0,0.35)", "transparent", colors.surface]} style={StyleFill} />
        </View>
        <View style={styles.body}>
          {career ? (
            <>
              <Badge label={career.category === "now" ? "Możesz zacząć już teraz" : "Wymaga nowych umiejętności"} />
              <Txt variant="display" testID="career-title">
                {career.title}
              </Txt>
              <View style={styles.metaRow}>
                <Badge label={`${career.match}% dopasowania`} tone="success" />
                {career.salary ? <Badge label={career.salary} tone="neutral" /> : null}
              </View>
              {career.why ? <Txt>{career.why}</Txt> : null}
            </>
          ) : null}

          {q.isLoading ? (
            <View style={styles.loading} testID="career-loading">
              <ActivityIndicator color={colors.brandPrimary} />
              <Txt>Przygotowuję opis zawodu na podstawie ofert pracy…</Txt>
            </View>
          ) : q.isError ? (
            <ErrorBox testID="career-error" message={(q.error as Error).message} onRetry={() => q.refetch()} />
          ) : d ? (
            <Animated.View entering={FadeIn.duration(400)} style={{ gap: spacing.xl }}>
              <Section title="Na czym polega ta praca" icon="document-text-outline">
                <Txt testID="career-description">{d.description}</Txt>
                <List items={d.daily_tasks} icon="ellipse" iconSize={8} color={colors.muted} />
              </Section>
              <View style={styles.proCon}>
                <View style={[styles.pcBox, { backgroundColor: colors.successTint }]} testID="career-pros">
                  <Text style={[styles.pcTitle, { color: colors.success }]}>Plusy</Text>
                  <List items={d.pros} icon="checkmark-circle" color={colors.success} />
                </View>
                <View style={[styles.pcBox, { backgroundColor: colors.errorTint }]} testID="career-cons">
                  <Text style={[styles.pcTitle, { color: colors.error }]}>Minusy</Text>
                  <List items={d.cons} icon="close-circle" color={colors.error} />
                </View>
              </View>
              <Section title="Wymagania z ofert pracy" icon="clipboard-outline">
                <List items={d.requirements} icon="checkbox-outline" color={colors.brandPrimary} />
              </Section>
              <Section title="Jak zacząć" icon="rocket-outline">
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
                <Section title="Możliwa ścieżka awansu" icon="trending-up-outline">
                  <Txt>{d.career_levels.join("  →  ")}</Txt>
                </Section>
              ) : null}
              <Section title="Zobacz aktualne oferty" icon="search-outline">
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
        </View>
      </ScrollView>

      <View style={[styles.topBar, { top: insets.top + spacing.sm }]}>
        <IconButton testID="career-back-button" icon="arrow-back" onPress={() => (router.canGoBack() ? router.back() : router.replace("/(tabs)"))} />
      </View>

      <View style={[styles.sticky, { paddingBottom: insets.bottom + spacing.md }]}>
        {chooseError ? <ErrorBox testID="choose-error" message={chooseError} /> : null}
        <Button testID="choose-path-button" title="Wybieram tę ścieżkę" icon="flag" onPress={choose} loading={choosing} disabled={!d} />
      </View>

      <Modal visible={celebrate} transparent animationType="fade" statusBarTranslucent>
        <View style={styles.overlay}>
          <Animated.View entering={ZoomIn.springify()} style={styles.celebrate} testID="celebration-modal">
            <View style={styles.celebrateIcon}>
              <Ionicons name="trophy" size={44} color={colors.onBrandPrimary} />
            </View>
            <Txt variant="title" style={{ textAlign: "center" }}>
              Świetny wybór!
            </Txt>
            <Txt style={{ textAlign: "center" }}>Buduję Twoją drogę do celu: {career?.title}</Txt>
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
  hero: { height: 220 },
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
