import { useRouter } from "expo-router";
import { useEffect, useRef, useState } from "react";
import { Modal, Text, TextInput, View } from "react-native";
import { KeyboardAwareScrollView, KeyboardStickyView } from "react-native-keyboard-controller";
import Animated, { ZoomIn } from "react-native-reanimated";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { useAds } from "@/src/ads/AdsProvider";
import { api } from "@/src/api";
import { useAuth } from "@/src/auth";
import { AiNote, Button, ErrorBox, IconButton, Ionicons, Txt } from "@/src/components/ui";
import { queryClient } from "@/src/query-client";
import { playSuccess } from "@/src/sound";
import { fonts, makeStyles, radius, spacing, useTheme } from "@/src/theme";

export default function CustomPath() {
  const insets = useSafeAreaInsets();
  const styles = useStyles();
  const { colors } = useTheme();
  const router = useRouter();
  const { showAds, watchRoadmapAd } = useAds();
  const { refresh } = useAuth();
  const [title, setTitle] = useState("");
  const [qualifications, setQualifications] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [celebrate, setCelebrate] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => () => {
    if (timer.current) clearTimeout(timer.current);
  }, []);

  const canSubmit = title.trim().length >= 2;

  const submit = async () => {
    if (!canSubmit || saving) return;
    setError("");
    if (!(await watchRoadmapAd("zbudować ścieżkę dla wskazanego stanowiska"))) return;
    setSaving(true);
    try {
      await api("/roadmap/custom", { method: "POST", body: { title: title.trim(), qualifications: qualifications.trim() } });
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
          <Txt>Napisz, do jakiego stanowiska mam ułożyć Twoją drogę kariery i plan nauki — bez ankiety.</Txt>
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
          {showAds ? (
            <Text style={styles.notice} testID="custom-path-ad-notice">
              Przed zbudowaniem ścieżki zobaczysz krótką reklamę.{" "}
              <Text style={styles.noticeLink} testID="custom-path-go-premium" onPress={() => router.push("/premium")} suppressHighlighting>
                Bez reklam z Premium.
              </Text>
            </Text>
          ) : null}
          <Button testID="custom-path-submit" title="Zbuduj moją drogę" icon="flag" onPress={submit} loading={saving} disabled={!canSubmit} />
        </View>
      </KeyboardStickyView>

      <Modal visible={celebrate} transparent animationType="fade" statusBarTranslucent>
        <View style={styles.overlay}>
          <Animated.View entering={ZoomIn.springify()} style={styles.celebrate} testID="custom-path-celebration-modal">
            <View style={styles.celebrateIcon}>
              <Ionicons name="trophy" size={44} color={colors.onBrandPrimary} />
            </View>
            <Txt variant="title" style={{ textAlign: "center" }}>
              Świetny wybór!
            </Txt>
            <Txt style={{ textAlign: "center" }}>Buduję Twoją drogę do celu: {title.trim()}</Txt>
          </Animated.View>
        </View>
      </Modal>
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
  notice: { fontFamily: fonts.medium, fontSize: 12, lineHeight: 17, color: c.muted, textAlign: "center" },
  noticeLink: { fontFamily: fonts.bold, color: c.brandPrimary },
  overlay: { flex: 1, backgroundColor: c.overlay, alignItems: "center", justifyContent: "center", padding: spacing.xl },
  celebrate: { backgroundColor: c.surface, borderRadius: radius.lg, padding: spacing.xxl, alignItems: "center", gap: spacing.md, width: "100%" },
  celebrateIcon: { width: 88, height: 88, borderRadius: 44, backgroundColor: c.brandPrimary, alignItems: "center", justifyContent: "center" },
}));
