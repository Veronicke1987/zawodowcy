import { useRouter } from "expo-router";
import { useState } from "react";
import { ActivityIndicator, View } from "react-native";
import Animated, { FadeInDown } from "react-native-reanimated";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { Ionicons, PressableScale, Txt } from "@/src/components/ui";
import { COUNTRIES, LOCAL_COUNTRY_KEY } from "@/src/countries";
import { useAuth } from "@/src/auth";
import { makeStyles, radius, spacing, useTheme } from "@/src/theme";
import { storage } from "@/src/utils/storage";

// Shown once, before the login/register screen, so new visitors pick their country/market up
// front (it decides the language and market context AI uses). Remembered locally so it never
// shows again on this device — changeable later from Profile once logged in.
export default function CountrySelect() {
  const insets = useSafeAreaInsets();
  const styles = useStyles();
  const { colors } = useTheme();
  const router = useRouter();
  const { setLocalCountry } = useAuth();
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
          Wybierz swój kraj
        </Txt>
        <Txt>Dopasujemy język, widełki wynagrodzeń i portale pracy do Twojego rynku. Zawsze możesz to zmienić później w profilu.</Txt>
      </View>
      <View style={{ paddingHorizontal: spacing.xl, gap: spacing.md, marginTop: spacing.xl }}>
        {COUNTRIES.map((c, i) => (
          <Animated.View key={c.code} entering={FadeInDown.delay(i * 40)}>
            <PressableScale testID={`country-select-option-${c.code}`} onPress={() => choose(c.code)} disabled={!!saving} style={styles.card}>
              <Txt style={styles.flag}>{c.flag}</Txt>
              <View style={{ flex: 1 }}>
                <Txt variant="heading">{c.name}</Txt>
                <Txt variant="caption">Treści AI w języku {c.lang}m</Txt>
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
