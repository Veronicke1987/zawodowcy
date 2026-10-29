// Design tokens for Zawodowcy. Three user-switchable themes (keys match the
// "color" block of /app/design_guidelines.json):
//   fresh = "Świeży i motywujący" (default), calm = "Spokojny i profesjonalny",
//   dark = "Ciemny i nowoczesny".
// Components use useTheme() or makeStyles(); never color literals.

import { useMemo, useSyncExternalStore } from "react";
import { Appearance, StyleSheet } from "react-native";

import { storage } from "@/src/utils/storage";

export type ColorScheme = "light" | "dark";
export type ThemeName = "fresh" | "calm" | "dark";

const fresh = {
  surface: "#FFFFFF",
  onSurface: "#1C1C1E",
  surfaceSecondary: "#F5F5F7",
  onSurfaceSecondary: "#3A3A3C",
  surfaceTertiary: "#E5E5EA",
  onSurfaceTertiary: "#1C1C1E",
  surfaceInverse: "#1C1C1E",
  onSurfaceInverse: "#FFFFFF",
  muted: "#8E8E93",
  brand: "#FF6B6B",
  onBrand: "#FFFFFF",
  brandPrimary: "#FA5252",
  onBrandPrimary: "#FFFFFF",
  brandSecondary: "#FF8787",
  onBrandSecondary: "#343A40",
  brandTertiary: "#FFE3E3",
  onBrandTertiary: "#E03131",
  success: "#2B8A3E",
  onSuccess: "#FFFFFF",
  warning: "#F59F00",
  onWarning: "#FFFFFF",
  error: "#C92A2A",
  onError: "#FFFFFF",
  info: "#1864AB",
  onInfo: "#FFFFFF",
  border: "#E5E5EA",
  borderStrong: "#C7C7CC",
  divider: "#E5E5EA",
  successTint: "#E6F4EA",
  errorTint: "#FDECEC",
  overlay: "rgba(0,0,0,0.45)",
};

export type ThemeColors = typeof fresh;

const calm: ThemeColors = {
  surface: "#FDFDFD",
  onSurface: "#2B2B2B",
  surfaceSecondary: "#F4F4F3",
  onSurfaceSecondary: "#4A4A4A",
  surfaceTertiary: "#EBEBE9",
  onSurfaceTertiary: "#2B2B2B",
  surfaceInverse: "#2B2B2B",
  onSurfaceInverse: "#FDFDFD",
  muted: "#8A8A8A",
  brand: "#8AA798",
  onBrand: "#FFFFFF",
  brandPrimary: "#728F81",
  onBrandPrimary: "#FFFFFF",
  brandSecondary: "#A3BCAD",
  onBrandSecondary: "#1F2923",
  brandTertiary: "#E1EAE4",
  onBrandTertiary: "#3B5246",
  success: "#406B54",
  onSuccess: "#FFFFFF",
  warning: "#D4A373",
  onWarning: "#1F2923",
  error: "#9E4747",
  onError: "#FFFFFF",
  info: "#4A6A8A",
  onInfo: "#FFFFFF",
  border: "#EBEBE9",
  borderStrong: "#D1D1CD",
  divider: "#EBEBE9",
  successTint: "#E3EEE7",
  errorTint: "#F4E6E6",
  overlay: "rgba(0,0,0,0.4)",
};

const dark: ThemeColors = {
  surface: "#121212",
  onSurface: "#E0E0E0",
  surfaceSecondary: "#1E1E1E",
  onSurfaceSecondary: "#B3B3B3",
  surfaceTertiary: "#2C2C2C",
  onSurfaceTertiary: "#E0E0E0",
  surfaceInverse: "#E0E0E0",
  onSurfaceInverse: "#121212",
  muted: "#8A8A8A",
  brand: "#D4AF37",
  onBrand: "#121212",
  brandPrimary: "#C4A02A",
  onBrandPrimary: "#121212",
  brandSecondary: "#E2C45F",
  onBrandSecondary: "#121212",
  brandTertiary: "#423A16",
  onBrandTertiary: "#EAD688",
  success: "#4CAF50",
  onSuccess: "#FFFFFF",
  warning: "#F57F17",
  onWarning: "#121212",
  error: "#EF5350",
  onError: "#FFFFFF",
  info: "#64B5F6",
  onInfo: "#121212",
  border: "#2C2C2C",
  borderStrong: "#4A4A4A",
  divider: "#2C2C2C",
  successTint: "#1B3320",
  errorTint: "#3A1C1C",
  overlay: "rgba(0,0,0,0.65)",
};

export const themes: Record<ThemeName, ThemeColors> = { fresh, calm, dark };

export const themeLabels: Record<ThemeName, { title: string; subtitle: string }> = {
  fresh: { title: "Świeży i motywujący", subtitle: "Jasne tło, energetyczne akcenty" },
  calm: { title: "Spokojny i profesjonalny", subtitle: "Stonowane kolory, dużo przestrzeni" },
  dark: { title: "Ciemny i nowoczesny", subtitle: "Ciemne tło, złote akcenty" },
};

export const fonts = {
  regular: "PJS-Regular",
  medium: "PJS-Medium",
  semibold: "PJS-SemiBold",
  bold: "PJS-Bold",
  extrabold: "PJS-ExtraBold",
};

export const spacing = { xs: 4, sm: 8, md: 12, lg: 16, xl: 24, xxl: 32, xxxl: 48 };
export const radius = { sm: 6, md: 12, lg: 20, pill: 999 };

// ---- theme store (persisted)
const THEME_KEY = "theme_name";
let current: ThemeName = "fresh";
const listeners = new Set<() => void>();

function apply(name: ThemeName) {
  current = name;
  Appearance.setColorScheme?.(name === "dark" ? "dark" : "light");
  listeners.forEach((l) => l());
}

export function setThemeName(name: ThemeName) {
  apply(name);
  storage.setItem(THEME_KEY, name);
}

export async function loadThemeName() {
  const saved = await storage.getItem(THEME_KEY, "fresh");
  if (saved === "fresh" || saved === "calm" || saved === "dark") apply(saved);
}

function subscribe(l: () => void) {
  listeners.add(l);
  return () => listeners.delete(l);
}

export function useTheme(): { scheme: ColorScheme; name: ThemeName; colors: ThemeColors } {
  const name = useSyncExternalStore(subscribe, () => current, () => current);
  return { name, scheme: name === "dark" ? "dark" : "light", colors: themes[name] };
}

export function makeStyles<T extends StyleSheet.NamedStyles<T> | StyleSheet.NamedStyles<any>>(
  factory: (colors: ThemeColors) => T & StyleSheet.NamedStyles<any>,
): () => T {
  return function useStyles(): T {
    const { colors } = useTheme();
    return useMemo(() => StyleSheet.create(factory(colors)), [colors]);
  };
}
