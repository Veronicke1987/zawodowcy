import { useRouter } from "expo-router";
import { Linking, ScrollView, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { IconButton, PressableScale, Txt } from "@/src/components/ui";
import { makeStyles, spacing, useTheme } from "@/src/theme";

// Public, unauthenticated privacy policy page. Reachable at /legal/privacy
// without login so it can be used as the "Privacy Policy URL" required by
// Google Play Console / App Store Connect.

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <View style={{ marginTop: spacing.xl, gap: spacing.xs }}>
      <Txt variant="heading">{title}</Txt>
      {children}
    </View>
  );
}

export default function PrivacyPolicy() {
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const { colors } = useTheme();
  const styles = useStyles();

  return (
    <View style={styles.root}>
      <View style={[styles.header, { paddingTop: insets.top + spacing.sm }]}>
        <IconButton
          testID="privacy-back-button"
          icon="arrow-back"
          onPress={() => (router.canGoBack() ? router.back() : router.replace("/legal"))}
        />
        <Txt variant="title" style={{ flex: 1 }}>
          Polityka prywatności
        </Txt>
      </View>
      <ScrollView contentContainerStyle={{ paddingHorizontal: spacing.xl, paddingBottom: insets.bottom + spacing.xxl }}>
        <Txt testID="privacy-updated-at">Ostatnia aktualizacja: czerwiec 2026</Txt>
        <Txt style={{ marginTop: spacing.sm }}>
          Niniejsza polityka prywatności opisuje, jakie dane zbieramy w aplikacji „Zawodowcy” (dalej: „Aplikacja”), w jakim celu je
          przetwarzamy oraz jakie masz prawa związane z ochroną swoich danych osobowych.
        </Txt>

        <Section title="1. Administrator danych">
          <Txt>
            Administratorem danych osobowych zbieranych w Aplikacji jest osoba prowadząca projekt „Zawodowcy”. We wszystkich sprawach
            dotyczących przetwarzania danych osobowych możesz skontaktować się pod adresem e-mail:
          </Txt>
          <PressableScale onPress={() => Linking.openURL("mailto:weronisia1987s@gmail.com")} testID="privacy-contact-email">
            <Txt style={{ color: colors.brandPrimary }}>weronisia1987s@gmail.com</Txt>
          </PressableScale>
        </Section>

        <Section title="2. Jakie dane zbieramy">
          <Txt>- Dane konta: imię, adres e-mail oraz hasło (przechowywane w formie zaszyfrowanej).</Txt>
          <Txt>- Odpowiedzi z ankiety profilującej (doświadczenie, umiejętności, zainteresowania) używane do dopasowania zawodów.</Txt>
          <Txt>- Wygenerowane ścieżki kariery, postęp w ich realizacji oraz plany nauki.</Txt>
          <Txt>- Treść wiadomości wysyłanych do czatu z doradcą AI.</Txt>
          <Txt>- Identyfikatory reklamowe urządzenia oraz dane techniczne wykorzystywane do wyświetlania reklam (Google AdMob).</Txt>
        </Section>

        <Section title="3. Cel przetwarzania danych">
          <Txt>- Świadczenie i utrzymanie konta w Aplikacji oraz zapewnienie jej działania.</Txt>
          <Txt>- Generowanie spersonalizowanych rekomendacji zawodowych, ścieżek kariery i planów nauki przy użyciu sztucznej inteligencji.</Txt>
          <Txt>- Udzielanie odpowiedzi w czacie z doradcą AI.</Txt>
          <Txt>- Wyświetlanie reklam oraz utrzymanie bezpłatnej wersji Aplikacji.</Txt>
          <Txt>- Analiza i poprawa działania Aplikacji.</Txt>
        </Section>

        <Section title="4. Udostępnianie danych podmiotom trzecim">
          <Txt>Do realizacji powyższych celów korzystamy z następujących dostawców usług (podmiotów przetwarzających dane):</Txt>
          <Txt>- Anthropic — przetwarza treść zapytań i wiadomości czatu w celu generowania rekomendacji i odpowiedzi AI.</Txt>
          <Txt>- Google AdMob — wyświetla reklamy w bezpłatnej wersji Aplikacji i może wykorzystywać identyfikatory reklamowe urządzenia.</Txt>
          <Txt>- Dostawca hostingu i bazy danych — przechowuje dane konta na bezpiecznych serwerach.</Txt>
          <Txt>Nie sprzedajemy danych osobowych użytkowników.</Txt>
        </Section>

        <Section title="5. Okres przechowywania danych">
          <Txt>
            Dane przechowujemy tak długo, jak długo konto pozostaje aktywne. Po usunięciu konta dane zostaną usunięte lub
            zanonimizowane, chyba że ich dalsze przechowywanie jest wymagane przepisami prawa.
          </Txt>
        </Section>

        <Section title="6. Twoje prawa">
          <Txt>Zgodnie z RODO przysługuje Ci prawo do:</Txt>
          <Txt>- dostępu do swoich danych oraz otrzymania ich kopii,</Txt>
          <Txt>- sprostowania (poprawienia) danych,</Txt>
          <Txt>- usunięcia danych („prawo do bycia zapomnianym”) — możesz o to poprosić mailowo,</Txt>
          <Txt>- ograniczenia lub sprzeciwu wobec przetwarzania,</Txt>
          <Txt>- przenoszenia danych,</Txt>
          <Txt>- wniesienia skargi do Prezesa Urzędu Ochrony Danych Osobowych (UODO).</Txt>
        </Section>

        <Section title="7. Reklamy">
          <Txt>
            W bezpłatnej wersji Aplikacji wyświetlane są reklamy dostarczane przez Google AdMob (reklamy nagradzane i
            pełnoekranowe). AdMob może wykorzystywać identyfikator reklamowy urządzenia do wyświetlania reklam oraz, jeśli wyrazisz
            zgodę, reklam spersonalizowanych. Zakup wersji Premium wyłącza wyświetlanie reklam.
          </Txt>
        </Section>

        <Section title="8. Dzieci">
          <Txt>Aplikacja nie jest kierowana do osób poniżej 16. roku życia i nie zbieramy świadomie danych takich osób.</Txt>
        </Section>

        <Section title="9. Zmiany w polityce prywatności">
          <Txt>
            Polityka może być okresowo aktualizowana. O istotnych zmianach poinformujemy w Aplikacji lub poprzez aktualizację daty
            na tej stronie.
          </Txt>
        </Section>

        <Section title="10. Kontakt">
          <Txt>W sprawach związanych z ochroną danych napisz na adres:</Txt>
          <PressableScale onPress={() => Linking.openURL("mailto:weronisia1987s@gmail.com")} testID="privacy-contact-email-bottom">
            <Txt style={{ color: colors.brandPrimary }}>weronisia1987s@gmail.com</Txt>
          </PressableScale>
        </Section>
      </ScrollView>
    </View>
  );
}

const useStyles = makeStyles((c) => ({
  root: { flex: 1, backgroundColor: c.surface },
  header: { flexDirection: "row", alignItems: "center", gap: spacing.md, paddingHorizontal: spacing.xl, paddingBottom: spacing.md },
}));
