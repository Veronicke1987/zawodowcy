import { Image } from "expo-image";
import { LinearGradient } from "expo-linear-gradient";
import { useRouter } from "expo-router";
import { useState } from "react";
import { Pressable, Text, TextInput, View } from "react-native";
import { KeyboardAwareScrollView } from "react-native-keyboard-controller";
import Animated, { FadeInDown } from "react-native-reanimated";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { useAuth } from "@/src/auth";
import { Button, ErrorBox, Txt } from "@/src/components/ui";
import { fonts, makeStyles, radius, spacing, useTheme } from "@/src/theme";

const HERO =
  "https://images.unsplash.com/photo-1606059979642-8390434af3d5?crop=entropy&cs=srgb&fm=jpg&ixlib=rb-4.1.0&q=85&w=1200";

export default function AuthScreen() {
  const insets = useSafeAreaInsets();
  const { colors } = useTheme();
  const styles = useStyles();
  const router = useRouter();
  const { login, register } = useAuth();
  const [mode, setMode] = useState<"login" | "register">("register");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const submit = async () => {
    setError("");
    if (mode === "register" && !email.includes("@")) return setError("Podaj poprawny adres e-mail.");
    if (mode === "login" && !email.trim()) return setError("Podaj e-mail lub login.");
    if (password.length < 6) return setError("Hasło musi mieć co najmniej 6 znaków.");
    setLoading(true);
    try {
      if (mode === "login") await login(email.trim(), password);
      else await register(name.trim(), email.trim(), password);
      router.replace("/");
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <View style={styles.root}>
      <KeyboardAwareScrollView
        bottomOffset={24}
        keyboardShouldPersistTaps="handled"
        contentContainerStyle={{ paddingBottom: insets.bottom + spacing.xl }}
      >
        <View style={styles.hero}>
          <Image source={{ uri: HERO }} style={{ flex: 1 }} contentFit="cover" transition={300} />
          <LinearGradient colors={["transparent", colors.surface]} style={styles.scrim} />
          <View style={[styles.heroText, { paddingTop: insets.top + spacing.lg }]}>
            <Text style={styles.logo} testID="app-logo">
              reset<Text style={{ color: colors.brandPrimary }}>.</Text>
            </Text>
          </View>
        </View>
        <Animated.View entering={FadeInDown.duration(500)} style={styles.body}>
          <Txt variant="display">{mode === "login" ? "Witaj z powrotem" : "Zacznij od nowa"}</Txt>
          <Txt style={{ marginTop: spacing.sm }}>
            {mode === "login"
              ? "Zaloguj się, aby wrócić do swoich zawodów i drogi kariery."
              : "Odpowiedz na kilka pytań, a pokażemy Ci zawody, które do Ciebie pasują — i drogę, jak do nich dojść."}
          </Txt>

          <View style={styles.segment}>
            {(["register", "login"] as const).map((m) => (
              <Pressable
                key={m}
                testID={`auth-mode-${m}`}
                onPress={() => {
                  setMode(m);
                  setError("");
                }}
                style={[styles.segBtn, mode === m && { backgroundColor: colors.surface }]}
              >
                <Text style={[styles.segText, { color: mode === m ? colors.onSurface : colors.muted }]}>
                  {m === "login" ? "Logowanie" : "Rejestracja"}
                </Text>
              </Pressable>
            ))}
          </View>

          {mode === "register" ? (
            <Field label="Imię" testID="auth-name-input" value={name} onChangeText={setName} placeholder="np. Anna" />
          ) : null}
          <Field
            label={mode === "login" ? "E-mail lub login" : "E-mail"}
            testID="auth-email-input"
            value={email}
            onChangeText={setEmail}
            placeholder={mode === "login" ? "twoj@email.pl lub login" : "twoj@email.pl"}
            keyboardType={mode === "login" ? "default" : "email-address"}
            autoCapitalize="none"
            autoCorrect={false}
          />
          <Field
            label="Hasło"
            testID="auth-password-input"
            value={password}
            onChangeText={setPassword}
            placeholder="Min. 6 znaków"
            secureTextEntry
            onSubmitEditing={submit}
          />
          {error ? <ErrorBox testID="auth-error" message={error} /> : null}
          <Button
            testID="auth-submit-button"
            title={mode === "login" ? "Zaloguj się" : "Utwórz konto"}
            onPress={submit}
            loading={loading}
            style={{ marginTop: spacing.sm }}
          />
        </Animated.View>
      </KeyboardAwareScrollView>
    </View>
  );
}

function Field({ label, ...props }: React.ComponentProps<typeof TextInput> & { label: string }) {
  const styles = useStyles();
  const { colors } = useTheme();
  return (
    <View style={{ gap: spacing.xs }}>
      <Txt variant="label">{label}</Txt>
      <TextInput {...props} placeholderTextColor={colors.muted} style={styles.input} />
    </View>
  );
}

const useStyles = makeStyles((c) => ({
  root: { flex: 1, backgroundColor: c.surface },
  hero: { height: 260 },
  scrim: { position: "absolute", left: 0, right: 0, bottom: 0, height: 160 },
  heroText: { position: "absolute", left: spacing.xl, top: 0 },
  logo: { fontFamily: fonts.extrabold, fontSize: 34, color: "#FFFFFF", letterSpacing: -1 },
  body: { paddingHorizontal: spacing.xl, gap: spacing.lg, marginTop: -spacing.xl },
  segment: { flexDirection: "row", backgroundColor: c.surfaceTertiary, borderRadius: radius.pill, padding: 4, marginTop: spacing.sm },
  segBtn: { flex: 1, height: 44, borderRadius: radius.pill, alignItems: "center", justifyContent: "center" },
  segText: { fontFamily: fonts.bold, fontSize: 14 },
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
}));
