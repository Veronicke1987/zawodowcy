import { useRouter } from "expo-router";
import { useState } from "react";
import { ActivityIndicator, View } from "react-native";
import Animated, { FadeInDown } from "react-native-reanimated";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { Ionicons, PressableScale, Txt } from "@/src/components/ui";
import { COUNTRIES, LOCAL_COUNTRY_KEY } from "@/src/countries";
import { UI_LANGUAGES } from "@/src/languages";
import { useAuth } from "@/src/auth";
import { makeStyles, radius, spacing, useTheme } from "@/src/theme";
import { storage } from "@/src/utils/storage";

// Shown once, before the login/register screen, so new visitors pick their job-market country
// up front. The interface LANGUAGE is a fully separate choice made right here too (see
// src/languages.ts) — picking a country only decides the labor market (salaries, job boards,
// local job-title names), never the language the app or AI content is written in.
// Both choices are remembered locally so this screen never shows again on this device —
// changeable independently later from Profile once logged in.
export default function CountrySelect() {
  const insets = useSafeAreaInsets();
  const styles = useStyles();
  const { colors } = useTheme();
  const router = useRouter();
  const { setLocalCountry, setLocalLanguage, lang, t } = useAuth();
  const [saving, setSaving] = useState<string | null>(null);

  const choose = async (code: string) => {
    if (saving) return;
    setSaving(code);
    await storage.setItem(LOCAL_COUNTRY_KEY, code);
    setLocalCountry(code);
    router.replace({ pathname: "/auth", params: { country: code } });
  };

  return (
    <View style={[styles.root, { paddingTop: insets.top + spacing.xxl, paddingBottom: insets.bottom + spacing.xl }]}>
      <View style={{ paddingHorizontal: spacing.xl, gap: spacing.sm }}>
        <Txt variant="display" testID="country-select-title">
          {t.countrySelect.title}
        </Txt>
        <Txt>{t.countrySelect.subtitle}</Txt>
      </View>

      <View style={{ paddingHorizontal: spacing.xl, marginTop: spacing.lg, gap: spacing.sm }}>
        <Txt variant="caption">{t.countrySelect.languageLabel}</Txt>
        <View style={{ flexDirection: "row", gap: spacing.sm }}>
          {UI_LANGUAGES.map((l) => {
            const selected = l.code === lang;
            return (
              <PressableScale
                key={l.code}
                testID={`country-select-language-${l.code}`}
                onPress={() => setLocalLanguage(l.code)}
                style={[styles.langChip, selected && { borderColor: colors.brandPrimary, backgroundColor: colors.brandTertiary }]}
              >
                <Txt style={styles.flag}>{l.flag}</Txt>
                <Txt variant="caption" style={selected ? { color: colors.onBrandTertiary, fontWeight: "700" } : undefined}>
                  {l.nativeName}
                </Txt>
              </PressableScale>
            );
          })}
        </View>
      </View>

      <View style={{ paddingHorizontal: spacing.xl, gap: spacing.md, marginTop: spacing.xl }}>
        {COUNTRIES.map((c, i) => (
          <Animated.View key={c.code} entering={FadeInDown.delay(i * 40)}>
            <PressableScale testID={`country-select-option-${c.code}`} onPress={() => choose(c.code)} disabled={!!saving} style={styles.card}>
              <Txt style={styles.flag}>{c.flag}</Txt>
              <View style={{ flex: 1 }}>
                <Txt variant="heading">{c.names[lang]}</Txt>
                <Txt variant="caption">{t.countrySelect.marketCaption}</Txt>
              </View>
              {saving === c.code ? <ActivityIndicator color={colors.brandPrimary} size="small" /> : <Ionicons name="chevron-forward" size={20} color={colors.muted} />}
            </PressableScale>
          </Animated.View>
        ))}
      </View>
    </View>
  );
}

const useStyles = makeStyles((c) => ({
  root: { flex: 1, backgroundColor: c.surface },
  flag: { fontSize: 30 },
  langChip: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.xs,
    paddingVertical: spacing.sm,
    borderRadius: radius.md,
    backgroundColor: c.surfaceSecondary,
    borderWidth: 1,
    borderColor: c.border,
    minHeight: 44,
  },
  card: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    padding: spacing.lg,
    borderRadius: radius.lg,
    backgroundColor: c.surfaceSecondary,
    borderWidth: 1,
    borderColor: c.border,
    minHeight: 64,
  },
}));
