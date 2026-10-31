import { LinearGradient } from "expo-linear-gradient";
import { useEffect, useState } from "react";
import { Text, View } from "react-native";
import Animated, { Easing, FadeIn, FadeInUp, FadeOut, useAnimatedStyle, useSharedValue, withRepeat, withTiming } from "react-native-reanimated";
import Svg, { Circle, Path } from "react-native-svg";

import { IconName, Ionicons } from "@/src/components/ui";
import { fonts, makeStyles, radius, spacing, useTheme } from "@/src/theme";

// Alternates office and non-office jobs so the hero shows the app is for every kind of work.
const JOBS: { title: string; area: string; icon: IconName; match: number }[] = [
  { title: "Specjalista ds. wdrożeń", area: "Biuro i IT", icon: "laptop", match: 92 },
  { title: "Elektryk", area: "Praca fizyczna", icon: "flash", match: 94 },
  { title: "Specjalista ds. kadr i płac", area: "Biuro i HR", icon: "people", match: 90 },
  { title: "Opiekun osób starszych", area: "Opieka i zdrowie", icon: "heart", match: 91 },
  { title: "Analityk danych", area: "Biuro i IT", icon: "bar-chart", match: 89 },
  { title: "Operator wózka widłowego", area: "Logistyka i magazyn", icon: "cube", match: 89 },
  { title: "Księgowa", area: "Biuro i finanse", icon: "calculator", match: 93 },
  { title: "Florysta", area: "Praca twórcza", icon: "flower", match: 90 },
  { title: "Specjalista ds. marketingu", area: "Biuro i media", icon: "megaphone", match: 88 },
  { title: "Kucharz", area: "Gastronomia", icon: "restaurant", match: 88 },
];

const SKILLS: { label: string; icon: IconName }[] = [
  { label: "Kurs Excela", icon: "laptop" },
  { label: "Prawo jazdy kat. C", icon: "car" },
  { label: "Angielski B2", icon: "language" },
  { label: "Uprawnienia SEP", icon: "flash" },
  { label: "Kurs księgowości", icon: "calculator" },
  { label: "Kurs opiekuna", icon: "heart" },
];

export function AuthHero({ topInset }: { topInset: number }) {
  const { colors } = useTheme();
  const styles = useStyles();
  const [i, setI] = useState(0);
  const float = useSharedValue(0);

  useEffect(() => {
    float.value = withRepeat(withTiming(1, { duration: 2600, easing: Easing.inOut(Easing.quad) }), -1, true);
    const t = setInterval(() => setI((x) => (x + 1) % JOBS.length), 2800);
    return () => clearInterval(t);
  }, [float]);
  const up = useAnimatedStyle(() => ({ transform: [{ translateY: -4 * float.value }] }));
  const job = JOBS[i];

  return (
    <View style={[styles.hero, { paddingTop: topInset + spacing.lg }]} testID="auth-hero">
      <LinearGradient colors={[colors.brandPrimary, colors.brandSecondary]} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={styles.fill} />
      <Svg style={styles.fill} viewBox="0 0 390 340" preserveAspectRatio="xMidYMid slice">
        <Circle cx={340} cy={60} r={110} fill={colors.onBrandPrimary} opacity={0.08} />
        <Circle cx={30} cy={300} r={90} fill={colors.onBrandPrimary} opacity={0.07} />
        <Path d="M -10 300 C 90 250, 140 300, 220 230 S 330 150, 400 120" stroke={colors.onBrandPrimary} strokeOpacity={0.35} strokeWidth={3} strokeDasharray="2,10" strokeLinecap="round" fill="none" />
      </Svg>

      <Text style={styles.logo} testID="app-logo" numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.6} maxFontSizeMultiplier={1.1}>
        Zawodowcy
      </Text>
      <Text style={styles.tagline} testID="app-tagline" numberOfLines={2} maxFontSizeMultiplier={1.2}>
        Zmiana zawodu i nowa ścieżka kariery — w każdej branży
      </Text>

      <Animated.View entering={FadeInUp.delay(150).duration(500)} style={{ marginTop: spacing.lg }}>
        <Animated.View style={[styles.mainCard, up]} testID="auth-hero-job">
          <Animated.View key={job.title} entering={FadeIn.duration(350)} exiting={FadeOut.duration(200)} style={styles.cardRow}>
            <View style={styles.cardIcon}>
              <Ionicons name={job.icon} size={22} color={colors.onBrandTertiary} />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.cardKicker} numberOfLines={1} maxFontSizeMultiplier={1.2}>
                {job.area.toUpperCase()}
              </Text>
              <Text style={styles.cardTitle} numberOfLines={2} maxFontSizeMultiplier={1.2}>
                {job.title}
              </Text>
            </View>
            <View style={styles.match}>
              <Text style={styles.matchText} maxFontSizeMultiplier={1.2}>
                {job.match}%
              </Text>
            </View>
          </Animated.View>
        </Animated.View>
      </Animated.View>

      <Animated.View entering={FadeInUp.delay(300).duration(500)} style={styles.skills}>
        {SKILLS.map((s) => (
          <View key={s.label} style={styles.chip}>
            <Ionicons name={s.icon} size={15} color={colors.brandPrimary} />
            <Text style={styles.chipText} numberOfLines={1} maxFontSizeMultiplier={1.2}>
              {s.label}
            </Text>
          </View>
        ))}
      </Animated.View>
    </View>
  );
}

const useStyles = makeStyles((c) => ({
  hero: {
    paddingHorizontal: spacing.xl,
    paddingBottom: spacing.xl,
    overflow: "hidden",
    borderBottomLeftRadius: 32,
    borderBottomRightRadius: 32,
  },
  fill: { position: "absolute", left: 0, right: 0, top: 0, bottom: 0 },
  logo: { fontFamily: fonts.extrabold, fontSize: 32, color: c.onBrandPrimary, letterSpacing: -1, alignSelf: "stretch" },
  tagline: { fontFamily: fonts.semibold, fontSize: 14, lineHeight: 19, color: c.onBrandPrimary, opacity: 0.92, marginTop: 2 },
  mainCard: {
    backgroundColor: c.surface,
    borderRadius: radius.lg,
    padding: spacing.md,
    minHeight: 76,
    justifyContent: "center",
    shadowColor: "#000",
    shadowOpacity: 0.18,
    shadowRadius: 16,
    shadowOffset: { width: 0, height: 8 },
    elevation: 6,
  },
  cardRow: { flexDirection: "row", alignItems: "center", gap: spacing.sm + 2 },
  cardIcon: { width: 44, height: 44, borderRadius: radius.md, backgroundColor: c.brandTertiary, alignItems: "center", justifyContent: "center" },
  cardKicker: { fontFamily: fonts.bold, fontSize: 10, letterSpacing: 0.8, color: c.muted },
  cardTitle: { fontFamily: fonts.bold, fontSize: 15, lineHeight: 20, color: c.onSurface },
  match: { backgroundColor: c.brandPrimary, borderRadius: radius.md, paddingHorizontal: 9, paddingVertical: 6 },
  matchText: { fontFamily: fonts.extrabold, fontSize: 15, color: c.onBrandPrimary },
  skills: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm, marginTop: spacing.lg },
  chip: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    backgroundColor: c.surface,
    borderRadius: radius.pill,
    paddingHorizontal: spacing.md,
    paddingVertical: 7,
    maxWidth: "100%",
  },
  chipText: { fontFamily: fonts.bold, fontSize: 12, color: c.onSurface, flexShrink: 1 },
}));
