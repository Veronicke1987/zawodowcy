import { Ionicons } from "@react-native-vector-icons/ionicons";
import * as Haptics from "expo-haptics";
import React from "react";
import { ActivityIndicator, Pressable, StyleProp, Text, TextProps, TextStyle, View, ViewStyle } from "react-native";
import Animated, { useAnimatedStyle, useSharedValue, withSpring } from "react-native-reanimated";

import { fonts, makeStyles, radius, spacing, useTheme } from "@/src/theme";

export type IconName = React.ComponentProps<typeof Ionicons>["name"];
export { Ionicons };

type Variant = "display" | "title" | "heading" | "body" | "label" | "caption";

export function Txt({ variant = "body", style, ...rest }: TextProps & { variant?: Variant }) {
  const styles = useTextStyles();
  return <Text {...rest} style={[styles[variant], style]} />;
}

const useTextStyles = makeStyles((c) => ({
  display: { fontFamily: fonts.extrabold, fontSize: 30, lineHeight: 36, color: c.onSurface, letterSpacing: -0.5 },
  title: { fontFamily: fonts.bold, fontSize: 24, lineHeight: 30, color: c.onSurface, letterSpacing: -0.3 },
  heading: { fontFamily: fonts.bold, fontSize: 17, lineHeight: 23, color: c.onSurface },
  body: { fontFamily: fonts.regular, fontSize: 15, lineHeight: 22, color: c.onSurfaceSecondary },
  label: { fontFamily: fonts.semibold, fontSize: 14, lineHeight: 19, color: c.onSurface },
  caption: { fontFamily: fonts.medium, fontSize: 12, lineHeight: 16, color: c.muted },
}));

const AnimatedPressable = Animated.createAnimatedComponent(Pressable);

export function PressableScale({
  children,
  style,
  onPress,
  disabled,
  testID,
  haptic = true,
}: {
  children: React.ReactNode;
  style?: StyleProp<ViewStyle>;
  onPress?: () => void;
  disabled?: boolean;
  testID?: string;
  haptic?: boolean;
}) {
  const scale = useSharedValue(1);
  const aStyle = useAnimatedStyle(() => ({ transform: [{ scale: scale.value }] }));
  return (
    <AnimatedPressable
      testID={testID}
      disabled={disabled}
      onPressIn={() => (scale.value = withSpring(0.97, { damping: 18, stiffness: 300 }))}
      onPressOut={() => (scale.value = withSpring(1, { damping: 18, stiffness: 300 }))}
      onPress={() => {
        if (haptic) Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light).catch(() => {});
        onPress?.();
      }}
      style={[style, aStyle]}
    >
      {children}
    </AnimatedPressable>
  );
}

export function Button({
  title,
  onPress,
  loading,
  disabled,
  variant = "primary",
  icon,
  testID,
  style,
}: {
  title: string;
  onPress?: () => void;
  loading?: boolean;
  disabled?: boolean;
  variant?: "primary" | "secondary" | "ghost";
  icon?: IconName;
  testID?: string;
  style?: StyleProp<ViewStyle>;
}) {
  const { colors } = useTheme();
  const styles = useButtonStyles();
  const bg = variant === "primary" ? colors.brandPrimary : variant === "secondary" ? colors.brandTertiary : "transparent";
  const fg = variant === "primary" ? colors.onBrandPrimary : variant === "secondary" ? colors.onBrandTertiary : colors.onSurface;
  return (
    <PressableScale
      testID={testID}
      onPress={onPress}
      disabled={disabled || loading}
      style={[styles.btn, { backgroundColor: bg, opacity: disabled ? 0.5 : 1 }, variant === "ghost" && styles.ghost, style]}
    >
      {loading ? (
        <ActivityIndicator color={fg} />
      ) : (
        <View style={styles.row}>
          {icon ? <Ionicons name={icon} size={20} color={fg} /> : null}
          <Text style={[styles.text, { color: fg }]}>{title}</Text>
        </View>
      )}
    </PressableScale>
  );
}

const useButtonStyles = makeStyles((c) => ({
  btn: { minHeight: 54, borderRadius: radius.pill, alignItems: "center", justifyContent: "center", paddingHorizontal: spacing.xl },
  ghost: { borderWidth: 1.5, borderColor: c.border },
  row: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  text: { fontFamily: fonts.bold, fontSize: 16 },
}));

export function Chip({
  label,
  selected,
  onPress,
  testID,
}: {
  label: string;
  selected?: boolean;
  onPress?: () => void;
  testID?: string;
}) {
  const { colors } = useTheme();
  const styles = useChipStyles();
  return (
    <Pressable
      testID={testID}
      onPress={() => {
        Haptics.selectionAsync().catch(() => {});
        onPress?.();
      }}
      style={[
        styles.chip,
        {
          backgroundColor: selected ? colors.brandPrimary : colors.surfaceSecondary,
          borderColor: selected ? colors.brandPrimary : colors.border,
        },
      ]}
    >
      {selected ? <Ionicons name="checkmark" size={16} color={colors.onBrandPrimary} /> : null}
      <Text style={[styles.text, { flexShrink: 1, color: selected ? colors.onBrandPrimary : colors.onSurface }]}>{label}</Text>
    </Pressable>
  );
}

const useChipStyles = makeStyles(() => ({
  chip: {
    minHeight: 44,
    paddingHorizontal: spacing.lg,
    borderRadius: radius.pill,
    borderWidth: 1.5,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    flexShrink: 0,
    maxWidth: "100%",
    paddingVertical: spacing.sm,
  },
  text: { fontFamily: fonts.semibold, fontSize: 14 },
}));

export function Badge({ label, tone = "brand", testID, style }: { label: string; tone?: "brand" | "success" | "warning" | "neutral"; testID?: string; style?: StyleProp<TextStyle> }) {
  const { colors } = useTheme();
  const map = {
    brand: [colors.brandTertiary, colors.onBrandTertiary],
    success: [colors.successTint, colors.success],
    warning: [colors.surfaceTertiary, colors.onSurfaceTertiary],
    neutral: [colors.surfaceSecondary, colors.onSurfaceSecondary],
  } as const;
  const [bg, fg] = map[tone];
  return (
    <Text
      testID={testID}
      style={[
        { backgroundColor: bg, color: fg, fontFamily: fonts.bold, fontSize: 12, paddingHorizontal: 10, paddingVertical: 4, borderRadius: radius.pill, overflow: "hidden", alignSelf: "flex-start" },
        style,
      ]}
    >
      {label}
    </Text>
  );
}

export function IconButton({ icon, onPress, testID }: { icon: IconName; onPress: () => void; testID?: string }) {
  const { colors } = useTheme();
  return (
    <PressableScale
      testID={testID}
      onPress={onPress}
      style={{ width: 44, height: 44, borderRadius: 22, alignItems: "center", justifyContent: "center", backgroundColor: colors.surfaceSecondary }}
    >
      <Ionicons name={icon} size={22} color={colors.onSurface} />
    </PressableScale>
  );
}

export function ErrorBox({ message, onRetry, testID }: { message: string; onRetry?: () => void; testID?: string }) {
  const { colors } = useTheme();
  return (
    <View testID={testID} style={{ backgroundColor: colors.errorTint, borderRadius: radius.md, padding: spacing.lg, gap: spacing.md }}>
      <View style={{ flexDirection: "row", gap: spacing.sm, alignItems: "flex-start" }}>
        <Ionicons name="alert-circle" size={20} color={colors.error} />
        <Text style={{ flex: 1, fontFamily: fonts.medium, color: colors.error, fontSize: 14, lineHeight: 20 }}>{message}</Text>
      </View>
      {onRetry ? <Button testID={`${testID}-retry`} title="Spróbuj ponownie" variant="ghost" onPress={onRetry} /> : null}
    </View>
  );
}
