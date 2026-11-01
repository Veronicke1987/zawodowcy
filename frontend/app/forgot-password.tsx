import { useRouter } from "expo-router";
import { useState } from "react";
import { Text, TextInput, View } from "react-native";
import { KeyboardAwareScrollView } from "react-native-keyboard-controller";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api } from "@/src/api";
import { useAuth } from "@/src/auth";
import { Button, ErrorBox, IconButton, Txt } from "@/src/components/ui";
import { fonts, makeStyles, radius, spacing, useTheme } from "@/src/theme";

export default function ForgotPassword() {
  const insets = useSafeAreaInsets();
  const styles = useStyles();
  const { colors } = useTheme();
  const router = useRouter();
  const { completeAuth, t } = useAuth();
  const [step, setStep] = useState<"email" | "reset">("email");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");

  const requestCode = async () => {
    setError("");
    if (!email.includes("@")) return setError(t.forgotPassword.invalidEmail);
    setLoading(true);
    try {
      const res = await api<{ message: string }>("/auth/forgot-password", { method: "POST", body: { email: email.trim() } });
      setInfo(res.message);
      setStep("reset");
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const resetPassword = async () => {
    setError("");
    if (code.trim().length !== 6) return setError(t.forgotPassword.invalidCode);
    if (newPassword.length < 6) return setError(t.forgotPassword.shortPassword);
    setLoading(true);
    try {
      const res = await api<any>("/auth/reset-password", { method: "POST", body: { email: email.trim(), code: code.trim(), new_password: newPassword } });
      await completeAuth(res);
      router.replace("/");
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <View style={styles.root}>
      <View style={[styles.header, { paddingTop: insets.top + spacing.sm }]}>
        <IconButton
          testID="forgot-password-back-button"
          icon="arrow-back"
          onPress={() => (step === "reset" ? setStep("email") : router.canGoBack() ? router.back() : router.replace("/auth"))}
        />
      </View>
      <KeyboardAwareScrollView
        bottomOffset={60}
        keyboardShouldPersistTaps="handled"
        contentContainerStyle={{ padding: spacing.xl, gap: spacing.lg, paddingBottom: insets.bottom + spacing.xl }}
      >
        {step === "email" ? (
          <>
            <View style={{ gap: spacing.sm }}>
              <Txt variant="display" testID="forgot-password-title">
                {t.forgotPassword.title}
              </Txt>
              <Txt>{t.forgotPassword.subtitle}</Txt>
            </View>
            <View style={{ gap: spacing.sm }}>
              <Txt variant="label">{t.forgotPassword.emailLabel}</Txt>
              <TextInput
                testID="forgot-password-email-input"
                value={email}
                onChangeText={setEmail}
                placeholder="you@email.com"
                placeholderTextColor={colors.muted}
                keyboardType="email-address"
                autoCapitalize="none"
                autoCorrect={false}
                style={styles.input}
                onSubmitEditing={requestCode}
              />
            </View>
            {error ? <ErrorBox testID="forgot-password-error" message={error} /> : null}
            <Button testID="forgot-password-send-code" title={t.forgotPassword.sendCode} onPress={requestCode} loading={loading} />
          </>
        ) : (
          <>
            <View style={{ gap: spacing.sm }}>
              <Txt variant="display" testID="reset-password-title">
                {t.forgotPassword.checkInboxTitle}
              </Txt>
              <Txt testID="reset-password-info">{info || t.forgotPassword.checkInboxInfo(email.trim())}</Txt>
            </View>
            <View style={{ gap: spacing.sm }}>
              <Txt variant="label">{t.forgotPassword.codeLabel}</Txt>
              <TextInput
                testID="reset-password-code-input"
                value={code}
                onChangeText={(v) => setCode(v.replace(/[^0-9]/g, "").slice(0, 6))}
                placeholder="123456"
                placeholderTextColor={colors.muted}
                keyboardType="number-pad"
                maxLength={6}
                style={[styles.input, { letterSpacing: 6, fontFamily: fonts.bold, fontSize: 20, textAlign: "center" }]}
              />
            </View>
            <View style={{ gap: spacing.sm }}>
              <Txt variant="label">{t.forgotPassword.newPasswordLabel}</Txt>
              <TextInput
                testID="reset-password-new-password-input"
                value={newPassword}
                onChangeText={setNewPassword}
                placeholder={t.forgotPassword.newPasswordPlaceholder}
                placeholderTextColor={colors.muted}
                secureTextEntry
                autoCapitalize="none"
                autoCorrect={false}
                spellCheck={false}
                textContentType="newPassword"
                style={styles.input}
                onSubmitEditing={resetPassword}
              />
            </View>
            {error ? <ErrorBox testID="reset-password-error" message={error} /> : null}
            <Button testID="reset-password-submit" title={t.forgotPassword.submit} onPress={resetPassword} loading={loading} />
            <Text testID="forgot-password-resend" style={styles.resend} onPress={requestCode} suppressHighlighting>
              {t.forgotPassword.resend}
            </Text>
          </>
        )}
      </KeyboardAwareScrollView>
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
  resend: { fontFamily: fonts.semibold, fontSize: 13, color: c.brandPrimary, textAlign: "center", marginTop: spacing.sm },
}));
