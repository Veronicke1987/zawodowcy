import { Redirect } from "expo-router";
import { useEffect, useState } from "react";
import { ActivityIndicator, View } from "react-native";

import { useAuth } from "@/src/auth";
import { LOCAL_COUNTRY_KEY } from "@/src/countries";
import { useTheme } from "@/src/theme";
import { storage } from "@/src/utils/storage";

export default function Index() {
  const { user, loading } = useAuth();
  const { colors } = useTheme();
  const [checkingCountry, setCheckingCountry] = useState(true);
  const [hasLocalCountry, setHasLocalCountry] = useState(false);

  useEffect(() => {
    if (user) {
      setCheckingCountry(false);
      return;
    }
    storage.getItem<string | null>(LOCAL_COUNTRY_KEY, null).then((v) => {
      setHasLocalCountry(!!v);
      setCheckingCountry(false);
    });
  }, [user]);

  if (loading || checkingCountry) {
    return (
      <View style={{ flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: colors.surface }}>
        <ActivityIndicator testID="app-loading" color={colors.brandPrimary} size="large" />
      </View>
    );
  }
  if (!user) return <Redirect href={hasLocalCountry ? "/auth" : "/country-select"} />;
  // Admins manage the app, they don't need a career-change profile — skip the onboarding
  // quiz entirely so a fresh admin account always lands straight in the app/admin panel.
  if (!user.has_profile && user.role !== "admin") return <Redirect href="/quiz" />;
  return <Redirect href="/(tabs)" />;
}
