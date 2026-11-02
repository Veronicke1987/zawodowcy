import { useRouter } from "expo-router";
import { useState } from "react";
import { View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { Button, Txt } from "@/src/components/ui";
import { SelectField } from "@/src/components/Select";
import { COUNTRIES, LOCAL_COUNTRY_KEY } from "@/src/countries";
import { UI_LANGUAGES } from "@/src/languages";
import { useAuth, PENDING_ACCOUNT_SYNC_KEY } from "@/src/auth";
import { makeStyles, spacing } from "@/src/theme";
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
  const router = useRouter();
  const { setLocalCountry, setLocalLanguage, localCountry, lang, t } = useAuth();
  const [pendingCountry, setPendingCountry] = useState(localCountry || COUNTRIES[0].code);
  const [saving, setSaving] = useState(false);

  const confirm = async () => {
    if (saving) return;
    setSaving(true);
    await storage.setItem(LOCAL_COUNTRY_KEY, pendingCountry);
    setLocalCountry(pendingCountry);
    // Marks this pick as "not yet applied to an account" — login()/register() consume and
    // clear this right after the very next successful auth, whichever account that ends up being.
    await storage.setItem(PENDING_ACCOUNT_SYNC_KEY, true);
    router.replace({ pathname: "/auth", params: { country: pendingCountry } });
  };

  return (
    <View style={[styles.root, { paddingTop: insets.top + spacing.xxl, paddingBottom: insets.bottom + spacing.xl }]}>
      <View style={{ paddingHorizontal: spacing.xl, gap: spacing.sm, flex: 1 }}>
        <Txt variant="display" testID="country-select-title">
          {t.countrySelect.title}
        </Txt>
        <Txt>{t.countrySelect.subtitle}</Txt>

        <View style={{ marginTop: spacing.lg, gap: spacing.xs }}>
          <Txt variant="caption">{t.countrySelect.languageLabel}</Txt>
          <SelectField
            testID="country-select-language"
            label={t.countrySelect.languageLabel}
            options={UI_LANGUAGES.map((l) => ({ code: l.code, flag: l.flag, label: l.nativeName }))}
            selectedCode={lang}
            onSelect={(code) => setLocalLanguage(code as (typeof UI_LANGUAGES)[number]["code"])}
          />
        </View>

        <View style={{ marginTop: spacing.lg, gap: spacing.xs }}>
          <Txt variant="caption">{t.countrySelect.marketCaption}</Txt>
          <SelectField
            testID="country-select-country"
            label={t.countrySelect.marketCaption}
            options={COUNTRIES.map((c) => ({ code: c.code, flag: c.flag, label: c.names[lang] }))}
            selectedCode={pendingCountry}
            onSelect={setPendingCountry}
          />
        </View>
      </View>

      <View style={{ paddingHorizontal: spacing.xl, marginTop: spacing.xl }}>
        <Button testID="country-select-continue" title={t.countrySelect.continueButton} onPress={confirm} loading={saving} />
      </View>
    </View>
  );
}

const useStyles = makeStyles((c) => ({
  root: { flex: 1, backgroundColor: c.surface },
}));
