import { QueryClientProvider } from "@tanstack/react-query";
import { useFonts } from "expo-font";
import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { useEffect, useState } from "react";
import { LogBox, StyleSheet } from "react-native";
import { GestureHandlerRootView } from "react-native-gesture-handler";
import { KeyboardProvider } from "react-native-keyboard-controller";

import { AuthProvider } from "@/src/auth";
import { ErrorBoundary } from "@/src/components/error-boundary";
import { queryClient } from "@/src/query-client";
import { loadThemeName, useTheme } from "@/src/theme";

// Disable logbox errors etc so that users can see the app
// and agent works as expected.
LogBox.ignoreAllLogs(true);

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

  if ((!fontsLoaded && !fontError) || !themeReady) return null;

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
              <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: colors.surface } }} />
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
});
