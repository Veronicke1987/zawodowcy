import { useRouter } from "expo-router";
import { useEffect, useState } from "react";
import { Modal, Text, View } from "react-native";
import Animated, { FadeIn } from "react-native-reanimated";

import { useAuth } from "@/src/auth";
import { Button, Ionicons } from "@/src/components/ui";
import { fonts, makeStyles, radius, spacing, useTheme } from "@/src/theme";

// Shown once per app launch (not persisted — re-appears every cold start, as requested),
// so every user always understands, in plain language, why some actions show an ad before
// AI generates anything personal for them.
let shownThisSession = false;

export function AiInfoModal() {
  const styles = useStyles();
  const { colors } = useTheme();
  const router = useRouter();
  const { user } = useAuth();
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (shownThisSession) return;
    shownThisSession = true;
    setVisible(true);
  }, []);

  const premium = !!user?.is_premium;
  const limit = user?.roadmap_generations_limit ?? 25;

  return (
    <Modal visible={visible} transparent animationType="fade" statusBarTranslucent>
      <View style={styles.overlay}>
        <Animated.View entering={FadeIn} style={styles.card} testID="ai-info-modal">
          <View style={styles.icon}>
            <Ionicons name="sparkles" size={32} color={colors.onBrandPrimary} />
          </View>
          <Text style={styles.title}>Zanim zaczniesz</Text>
          <Text style={styles.body}>
            Twoja ścieżka kariery, plan nauki i opisy zawodów są tworzone przez sztuczną inteligencję specjalnie dla
            Ciebie — na podstawie Twoich odpowiedzi.
          </Text>
          <Text style={styles.body}>
            Każde takie „myślenie” AI kosztuje prawdziwe pieniądze (tzw. tokeny). Dlatego{" "}
            {premium ? "po wykorzystaniu Twojego miesięcznego limitu " : ""}
            tworzenie nowej ścieżki kariery lub planu nauki poprzedza krótka reklama — to dzięki niej aplikacja
            pozostaje darmowa.
          </Text>
          {premium ? (
            <Text style={styles.body} testID="ai-info-premium-note">
              Masz Premium: {limit} nowych ścieżek kariery miesięcznie bez reklam (plan do nich zawsze gratis).
            </Text>
          ) : (
            <Text style={styles.body}>
              Z Premium (19 zł/mies.) znikają reklamy i masz {limit} nowych ścieżek kariery miesięcznie bez czekania.
            </Text>
          )}
          <View style={{ gap: spacing.sm, width: "100%", marginTop: spacing.sm }}>
            {!premium ? (
              <Button
                testID="ai-info-go-premium"
                title="Przejdź na Premium"
                icon="diamond"
                onPress={() => {
                  setVisible(false);
                  router.push("/premium");
                }}
              />
            ) : null}
            <Button
              testID="ai-info-dismiss"
              title="Rozumiem, zaczynajmy"
              variant={premium ? "primary" : "ghost"}
              onPress={() => setVisible(false)}
            />
          </View>
        </Animated.View>
      </View>
    </Modal>
  );
}

const useStyles = makeStyles((c) => ({
  overlay: { flex: 1, backgroundColor: c.overlay, alignItems: "center", justifyContent: "center", padding: spacing.xl },
  card: { backgroundColor: c.surface, borderRadius: radius.lg, padding: spacing.xl, alignItems: "center", gap: spacing.sm, width: "100%", maxWidth: 380 },
  icon: { width: 64, height: 64, borderRadius: 32, backgroundColor: c.brandPrimary, alignItems: "center", justifyContent: "center", marginBottom: spacing.xs },
  title: { fontFamily: fonts.extrabold, fontSize: 19, color: c.onSurface, textAlign: "center" },
  body: { fontFamily: fonts.medium, fontSize: 13.5, lineHeight: 19, color: c.muted, textAlign: "center" },
}));
