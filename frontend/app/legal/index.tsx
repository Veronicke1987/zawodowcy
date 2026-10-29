import { useRouter } from "expo-router";
import { Linking, ScrollView, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { Button, Ionicons, PressableScale, Txt } from "@/src/components/ui";
import { makeStyles, radius, spacing, useTheme } from "@/src/theme";

// Public, unauthenticated "website" landing page for the app. Reachable at
// /legal without login so it can be used as the "Website URL" in app store
// listings (Google Play Console, App Store Connect).

const FEATURES: { icon: React.ComponentProps<typeof Ionicons>["name"]; title: string; text: string }[] = [
  { icon: "compass", title: "Profil zawodowy", text: "Krótka ankieta dopasowuje zawody do Twoich umiejętności i zainteresowań." },
  { icon: "trending-up", title: "Ścieżka kariery", text: "Wizualna mapa kroków — od miejsca, w którym jesteś, do nowego zawodu." },
  { icon: "book", title: "Plan nauki", text: "Tygodniowy plan kursów, szkoleń i działań, które przybliżają do celu." },
  { icon: "chatbubbles", title: "Doradca AI", text: "Czat z asystentem AI, który odpowiada na pytania o zmianę zawodu." },
];

export default function LegalHome() {
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const { colors } = useTheme();
  const styles = useStyles();

  return (
    <View style={styles.root}>
      <ScrollView contentContainerStyle={{ paddingTop: insets.top + spacing.xl, paddingBottom: insets.bottom + spacing.xxl }}>
        <View style={styles.hero}>
          <Txt variant="display" style={{ textAlign: "center" }} testID="legal-app-name">
            zawodowcy<Txt variant="display" style={{ color: colors.brandPrimary }}>.</Txt>
          </Txt>
          <Txt style={{ textAlign: "center", marginTop: spacing.sm }}>
            Aplikacja mobilna, która pomaga znaleźć nowy zawód i pokazuje, krok po kroku, jak go zdobyć.
          </Txt>
        </View>

        <View style={styles.cards}>
          {FEATURES.map((f) => (
            <View key={f.title} style={styles.card}>
              <View style={styles.cardIcon}>
                <Ionicons name={f.icon} size={20} color={colors.onBrandTertiary} />
              </View>
              <View style={{ flex: 1 }}>
                <Txt variant="heading">{f.title}</Txt>
                <Txt style={{ marginTop: 2 }}>{f.text}</Txt>
              </View>
            </View>
          ))}
        </View>

        <View style={styles.section}>
          <Txt variant="heading">Kontakt</Txt>
          <PressableScale onPress={() => Linking.openURL("mailto:weronisia1987s@gmail.com")} testID="legal-contact-email">
            <Txt style={{ color: colors.brandPrimary, marginTop: spacing.xs }}>weronisia1987s@gmail.com</Txt>
          </PressableScale>
        </View>

        <View style={{ paddingHorizontal: spacing.xl, gap: spacing.md, marginTop: spacing.xl }}>
          <Button testID="legal-privacy-link" title="Polityka prywatności" variant="secondary" icon="document-text" onPress={() => router.push("/legal/privacy")} />
          <Button testID="legal-open-app" title="Otwórz aplikację" variant="ghost" icon="arrow-forward" onPress={() => router.replace("/")} />
        </View>
      </ScrollView>
    </View>
  );
}

const useStyles = makeStyles((c) => ({
  root: { flex: 1, backgroundColor: c.surface },
  hero: { paddingHorizontal: spacing.xl },
  cards: { paddingHorizontal: spacing.xl, gap: spacing.md, marginTop: spacing.xxl },
  card: { flexDirection: "row", gap: spacing.md, backgroundColor: c.surfaceSecondary, borderRadius: radius.lg, padding: spacing.lg, alignItems: "flex-start" },
  cardIcon: { width: 40, height: 40, borderRadius: radius.md, backgroundColor: c.brandTertiary, alignItems: "center", justifyContent: "center" },
  section: { paddingHorizontal: spacing.xl, marginTop: spacing.xxl },
}));
