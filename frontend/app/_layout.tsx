import { QueryClientProvider } from "@tanstack/react-query";
import { useFonts } from "expo-font";
import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { useEffect, useState } from "react";
import { Image, LogBox, StyleSheet, Text, View } from "react-native";
import { GestureHandlerRootView } from "react-native-gesture-handler";
import { KeyboardProvider } from "react-native-keyboard-controller";

import { AdsProvider } from "@/src/ads/AdsProvider";
import { AuthProvider } from "@/src/auth";
import { ErrorBoundary } from "@/src/components/error-boundary";
import { queryClient } from "@/src/query-client";
import { loadThemeName, useTheme } from "@/src/theme";

// Disable logbox errors etc so that users can see the app
// and agent works as expected.
LogBox.ignoreAllLogs(true);

// Shown for the brief window between the native splash screen handing off to JS and
// our fonts/theme finishing loading. Matches app.json's native splash (same brand coral
// background + logo) so there's no flash of blank white in between.
function AppBootSplash() {
  return (
    <View style={styles.boot} testID="app-boot-splash">
      <Image source={require("../assets/images/icon.png")} style={styles.bootIcon} />
      <Text style={styles.bootTitle}>Zawodowcy</Text>
    </View>
  );
}

export default function RootLayout() {
  const { colors, scheme } = useTheme();
  const [themeReady, setThemeReady] = useState(false);
  const [fontsLoaded, fontError] = useFonts({
    "PJS-Regular": require("../assets/fonts/PlusJakartaSans-Regular.ttf"),
    "PJS-Medium": require("../assets/fonts/PlusJakartaSans-Medium.ttf"),
    "PJS-SemiBold": require("../assets/fonts/PlusJakartaSans-SemiBold.ttf"),
    "PJS-Bold": require("../assets/fonts/PlusJakartaSans-Bold.ttf"),
    "PJS-ExtraBold": require("../assets/fonts/PlusJakartaSans-ExtraBold.ttf"),
  });

  useEffect(() => {
    loadThemeName().finally(() => setThemeReady(true));
  }, []);

  if ((!fontsLoaded && !fontError) || !themeReady) return <AppBootSplash />;

  // One app level ErrorBoundary; a render crash shows a reload screen
  // instead of a blank app. GestureHandlerRootView must wrap the whole tree
  // or any gesture/swipe/drawer screen crashes in Expo Go.
  return (
    <GestureHandlerRootView style={[styles.root, { backgroundColor: colors.surface }]}>
      <ErrorBoundary>
        <QueryClientProvider client={queryClient}>
          <AuthProvider>
            <KeyboardProvider>
              <StatusBar style={scheme === "dark" ? "light" : "dark"} />
              <AdsProvider>
                <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: colors.surface } }} />
              </AdsProvider>
            </KeyboardProvider>
          </AuthProvider>
        </QueryClientProvider>
      </ErrorBoundary>
    </GestureHandlerRootView>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
  },
  // #FA5252 matches app.json's expo-splash-screen backgroundColor exactly, so the
  // native splash and this JS boot screen blend into one seamless brand moment.
  boot: { flex: 1, backgroundColor: "#FA5252", alignItems: "center", justifyContent: "center", gap: 16 },
  bootIcon: { width: 88, height: 88, borderRadius: 22 },
  bootTitle: { color: "#FFFFFF", fontSize: 28, fontWeight: "800", letterSpacing: -1 },
});
