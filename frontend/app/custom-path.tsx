import { useRouter } from "expo-router";
import { useState } from "react";
import { TextInput, View } from "react-native";
import { KeyboardAwareScrollView, KeyboardStickyView } from "react-native-keyboard-controller";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api } from "@/src/api";
import { AiNote, Button, ErrorBox, IconButton, Txt } from "@/src/components/ui";
import { queryClient } from "@/src/query-client";
import { fonts, makeStyles, radius, spacing, useTheme } from "@/src/theme";

export default function CustomPath() {
  const insets = useSafeAreaInsets();
  const styles = useStyles();
  const { colors } = useTheme();
  const router = useRouter();
  const [title, setTitle] = useState("");
  const [qualifications, setQualifications] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const canSubmit = title.trim().length >= 2;

  const submit = async () => {
    if (!canSubmit || saving) return;
    setError("");
    setSaving(true);
    try {
      const res = await api<{ career_id: string }>("/careers/custom", { method: "POST", body: { title: title.trim(), qualifications: qualifications.trim() } });
      queryClient.invalidateQueries({ queryKey: ["recommendations"] });
      router.replace(`/career/${res.career_id}`);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <View style={styles.root}>
      <View style={[styles.header, { paddingTop: insets.top + spacing.sm }]}>
        <IconButton testID="custom-path-back-button" icon="arrow-back" onPress={() => (router.canGoBack() ? router.back() : router.replace("/(tabs)"))} />
      </View>

      <KeyboardAwareScrollView
        bottomOffset={110}
        keyboardShouldPersistTaps="handled"
        contentContainerStyle={{ padding: spacing.xl, paddingBottom: 160 + insets.bottom, gap: spacing.xl }}
      >
        <View style={{ gap: spacing.sm }}>
          <Txt variant="display" testID="custom-path-title">
            Podaj stanowisko
          </Txt>
          <Txt>Napisz, do jakiego stanowiska Cię interesuje — zobaczysz jego kartę zawodu, a stamtąd zbudujesz drogę kariery i plan nauki.</Txt>
        </View>

        <View style={{ gap: spacing.sm }}>
          <Txt variant="label">Stanowisko</Txt>
          <TextInput
            testID="custom-path-input-title"
            value={title}
            onChangeText={setTitle}
            placeholder="np. Grafik komputerowy"
            placeholderTextColor={colors.muted}
            style={styles.input}
            maxLength={120}
            returnKeyType="next"
          />
        </View>

        <View style={{ gap: spacing.sm }}>
          <Txt variant="label">Twoje kwalifikacje (opcjonalnie)</Txt>
          <Txt variant="caption">
            Jakie masz już wykształcenie, doświadczenie lub kursy związane z tym stanowiskiem? Jeśli nic nie masz, zostaw puste — uwzględnimy to w
            planie.
          </Txt>
          <TextInput
            testID="custom-path-input-qualifications"
            value={qualifications}
            onChangeText={setQualifications}
            placeholder="np. brak doświadczenia w tym kierunku, albo: ukończony kurs… / 2 lata pracy jako…"
            placeholderTextColor={colors.muted}
            multiline
            style={[styles.input, { minHeight: 120, textAlignVertical: "top", paddingTop: spacing.md }]}
            maxLength={1000}
          />
        </View>

        {error ? <ErrorBox testID="custom-path-error" message={error} /> : null}
        <AiNote />
      </KeyboardAwareScrollView>

      <KeyboardStickyView offset={{ opened: insets.bottom }} style={styles.sticky}>
        <View style={[styles.stickyInner, { paddingBottom: insets.bottom + spacing.md }]}>
          <Button testID="custom-path-submit" title="Zobacz ten zawód" icon="search" onPress={submit} loading={saving} disabled={!canSubmit} />
        </View>
      </KeyboardStickyView>
    </View>
  );
}

const useStyles = makeStyles((c) => ({
  root: { flex: 1, backgroundColor: c.surface },
  header: { paddingHorizontal: spacing.xl, paddingBottom: spacing.sm, backgroundColor: c.surface },
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
}));
