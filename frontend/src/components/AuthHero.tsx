import { LinearGradient } from "expo-linear-gradient";
import { useEffect } from "react";
import { Text, View } from "react-native";
import Animated, { FadeInUp, useAnimatedStyle, useSharedValue, withRepeat, withTiming, Easing } from "react-native-reanimated";
import Svg, { Circle, Path } from "react-native-svg";

import { Ionicons } from "@/src/components/ui";
import { fonts, makeStyles, radius, spacing, useTheme } from "@/src/theme";

// Theme-aware hero for the auth screen: brand gradient + floating "app preview" cards.
export function AuthHero({ topInset }: { topInset: number }) {
  const { colors } = useTheme();
  const styles = useStyles();
  const float = useSharedValue(0);
  useEffect(() => {
    float.value = withRepeat(withTiming(1, { duration: 2600, easing: Easing.inOut(Easing.quad) }), -1, true);
  }, [float]);
  const up = useAnimatedStyle(() => ({ transform: [{ translateY: -6 * float.value }] }));
  const down = useAnimatedStyle(() => ({ transform: [{ translateY: 6 * float.value }] }));

  return (
    <View style={[styles.hero, { paddingTop: topInset + spacing.lg }]} testID="auth-hero">
      <LinearGradient colors={[colors.brandPrimary, colors.brandSecondary]} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={styles.fill} />
      <Svg style={styles.fill} viewBox="0 0 390 340" preserveAspectRatio="xMidYMid slice">
        <Circle cx={340} cy={60} r={110} fill={colors.onBrandPrimary} opacity={0.08} />
        <Circle cx={30} cy={300} r={90} fill={colors.onBrandPrimary} opacity={0.07} />
        <Path d="M -10 300 C 90 250, 140 300, 220 230 S 330 150, 400 120" stroke={colors.onBrandPrimary} strokeOpacity={0.35} strokeWidth={3} strokeDasharray="2,10" strokeLinecap="round" fill="none" />
      </Svg>

      <Text style={styles.logo} testID="app-logo">
        reset<Text style={{ color: colors.onBrandPrimary, opacity: 0.6 }}>.</Text>
      </Text>
      <Text style={styles.tagline} testID="app-tagline">
        Zmiana zawodu i nowa ścieżka kariery
      </Text>

      <View style={styles.stage}>
        <Animated.View entering={FadeInUp.delay(150).duration(500)} style={[styles.mainCard, up]}>
          <View style={styles.cardIcon}>
            <Ionicons name="briefcase" size={20} color={colors.onBrandTertiary} />
          </View>
          <View style={{ flex: 1 }}>
            <Text style={styles.cardKicker}>DOPASOWANY ZAWÓD</Text>
            <Text style={styles.cardTitle} numberOfLines={1}>
              Specjalista ds. wdrożeń
            </Text>
          </View>
          <View style={styles.match}>
            <Text style={styles.matchText}>92%</Text>
          </View>
        </Animated.View>

        <Animated.View entering={FadeInUp.delay(300).duration(500)} style={[styles.chip, styles.chipLeft, down]}>
          <Ionicons name="checkmark-circle" size={18} color={colors.success} />
          <Text style={styles.chipText}>Kurs Excela</Text>
        </Animated.View>

        <Animated.View entering={FadeInUp.delay(450).duration(500)} style={[styles.chip, styles.chipRight, up]}>
          <Ionicons name="trending-up" size={18} color={colors.brandPrimary} />
          <Text style={styles.chipText}>Awans: kierownik</Text>
        </Animated.View>
      </View>
    </View>
  );
}

const useStyles = makeStyles((c) => ({
  hero: { height: 340, paddingHorizontal: spacing.xl, overflow: "hidden", borderBottomLeftRadius: 32, borderBottomRightRadius: 32 },
  fill: { position: "absolute", left: 0, right: 0, top: 0, bottom: 0 },
  logo: { fontFamily: fonts.extrabold, fontSize: 34, color: c.onBrandPrimary, letterSpacing: -1 },
  tagline: { fontFamily: fonts.semibold, fontSize: 15, color: c.onBrandPrimary, opacity: 0.92, marginTop: 2 },
  stage: { flex: 1, marginTop: spacing.lg },
  mainCard: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    backgroundColor: c.surface,
    borderRadius: radius.lg,
    padding: spacing.md,
    marginTop: spacing.sm,
    shadowColor: "#000",
    shadowOpacity: 0.18,
    shadowRadius: 16,
    shadowOffset: { width: 0, height: 8 },
    elevation: 6,
  },
  cardIcon: { width: 40, height: 40, borderRadius: radius.md, backgroundColor: c.brandTertiary, alignItems: "center", justifyContent: "center" },
  cardKicker: { fontFamily: fonts.bold, fontSize: 10, letterSpacing: 1, color: c.muted },
  cardTitle: { fontFamily: fonts.bold, fontSize: 15, color: c.onSurface },
  match: { backgroundColor: c.brandPrimary, borderRadius: radius.md, paddingHorizontal: 10, paddingVertical: 6 },
  matchText: { fontFamily: fonts.extrabold, fontSize: 15, color: c.onBrandPrimary },
  chip: {
    position: "absolute",
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    backgroundColor: c.surface,
    borderRadius: radius.pill,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    shadowColor: "#000",
    shadowOpacity: 0.15,
    shadowRadius: 10,
    shadowOffset: { width: 0, height: 6 },
    elevation: 4,
  },
  chipLeft: { left: 0, top: 92 },
  chipRight: { right: 0, top: 128 },
  chipText: { fontFamily: fonts.bold, fontSize: 13, color: c.onSurface },
}));
