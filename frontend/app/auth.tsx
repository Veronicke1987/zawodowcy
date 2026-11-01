import { useLocalSearchParams, useRouter } from "expo-router";
import { useEffect, useState } from "react";
import { Pressable, Text, TextInput, View } from "react-native";
import { KeyboardAwareScrollView } from "react-native-keyboard-controller";
import Animated, { FadeInDown } from "react-native-reanimated";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { useAuth } from "@/src/auth";
import { AuthHero } from "@/src/components/AuthHero";
import { Button, ErrorBox, Ionicons, Txt } from "@/src/components/ui";
import { LOCAL_COUNTRY_KEY } from "@/src/countries";
import { fonts, makeStyles, radius, spacing, useTheme } from "@/src/theme";
import { storage } from "@/src/utils/storage";

const FEATURE_ICONS = ["briefcase", "trending-up", "school"] as const;

export default function AuthScreen() {
  const insets = useSafeAreaInsets();
  const { colors } = useTheme();
  const styles = useStyles();
  const router = useRouter();
  const { country: countryParam } = useLocalSearchParams<{ country?: string }>();
  const { login, register, t } = useAuth();
  const [mode, setMode] = useState<"login" | "register">("register");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [country, setCountry] = useState<string | undefined>(countryParam);

  useEffect(() => {
    if (countryParam) return;
    storage.getItem<string | null>(LOCAL_COUNTRY_KEY, null).then((v) => v && setCountry(v));
  }, [countryParam]);

  const submit = async () => {
    setError("");
    if (mode === "register" && !email.includes("@")) return setError(t.auth.invalidEmail);
    if (mode === "login" && !email.trim()) return setError(t.auth.invalidLoginId);
    if (password.length < 6) return setError(t.auth.shortPassword);
    setLoading(true);
    try {
      if (mode === "login") await login(email.trim(), password);
      else await register(name.trim(), email.trim(), password, country);
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
        <AuthHero topInset={insets.top} />
        <Animated.View entering={FadeInDown.duration(500)} style={styles.body}>
          <Txt variant="display">{mode === "login" ? t.auth.welcomeBackTitle : t.auth.findCareerTitle}</Txt>
          <Txt style={{ marginTop: spacing.sm }}>{mode === "login" ? t.auth.loginSubtitle : t.auth.registerSubtitle}</Txt>
          {mode === "register" ? (
            <View style={{ gap: spacing.sm }} testID="auth-features">
              {FEATURE_ICONS.map((icon, i) => (
                <View key={icon} style={styles.feature}>
                  <View style={styles.featureIcon}>
                    <Ionicons name={icon} size={18} color={colors.onBrandTertiary} />
                  </View>
                  <Text style={styles.featureText}>{t.auth.features[i]}</Text>
                </View>
              ))}
            </View>
          ) : null}

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
                  {m === "login" ? t.auth.loginTab : t.auth.registerTab}
                </Text>
              </Pressable>
            ))}
          </View>

          {mode === "register" ? (
            <Field label={t.auth.nameLabel} testID="auth-name-input" value={name} onChangeText={setName} placeholder={t.auth.namePlaceholder} />
          ) : null}
          <Field
            label={mode === "login" ? t.auth.emailLabelLogin : t.auth.emailLabel}
            testID="auth-email-input"
            value={email}
            onChangeText={setEmail}
            placeholder={mode === "login" ? t.auth.emailPlaceholderLogin : t.auth.emailPlaceholderLogin}
            keyboardType={mode === "login" ? "default" : "email-address"}
            autoCapitalize="none"
            autoCorrect={false}
          />
          <Field
            label={t.auth.passwordLabel}
            testID="auth-password-input"
            value={password}
            onChangeText={setPassword}
            placeholder={t.auth.passwordPlaceholder}
            secureTextEntry
            autoCapitalize="none"
            autoCorrect={false}
            spellCheck={false}
            textContentType={mode === "login" ? "password" : "newPassword"}
            onSubmitEditing={submit}
          />
          {mode === "login" ? (
            <Pressable
              testID="auth-forgot-password-link"
              onPress={() => router.push("/forgot-password")}
              style={{ alignSelf: "flex-end" }}
              hitSlop={8}
            >
              <Text style={styles.forgotLink}>{t.auth.forgotPassword}</Text>
            </Pressable>
          ) : null}
          {error ? <ErrorBox testID="auth-error" message={error} /> : null}
          <Button
            testID="auth-submit-button"
            title={mode === "login" ? t.auth.loginButton : t.auth.registerButton}
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
  feature: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  featureIcon: { width: 32, height: 32, borderRadius: radius.sm, backgroundColor: c.brandTertiary, alignItems: "center", justifyContent: "center" },
  featureText: { flex: 1, fontFamily: fonts.semibold, fontSize: 14, color: c.onSurface },
  body: { paddingHorizontal: spacing.xl, gap: spacing.lg, marginTop: spacing.xl },
  segment: { flexDirection: "row", backgroundColor: c.surfaceTertiary, borderRadius: radius.pill, padding: 4, marginTop: spacing.sm },
  segBtn: { flex: 1, height: 44, borderRadius: radius.pill, alignItems: "center", justifyContent: "center" },
  segText: { fontFamily: fonts.bold, fontSize: 14 },
  forgotLink: { fontFamily: fonts.semibold, fontSize: 13, color: c.brandPrimary },
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
