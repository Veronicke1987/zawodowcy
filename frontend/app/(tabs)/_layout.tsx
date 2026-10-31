import { Ionicons } from "@react-native-vector-icons/ionicons";
import { Redirect, Tabs } from "expo-router";
import { NativeTabs } from "expo-router/native-tabs";
import { Platform } from "react-native";

import { useAuth } from "@/src/auth";
import { AiInfoModal } from "@/src/components/AiInfoModal";
import { usesNativeTabs } from "@/src/navigation";
import { fonts, useTheme } from "@/src/theme";

export default function TabsLayout() {
  const { user, loading } = useAuth();
  const { colors } = useTheme();
  if (!loading && !user) return <Redirect href="/auth" />;

  if (usesNativeTabs) {
    return (
      <>
        <AiInfoModal />
        <NativeTabs tintColor={colors.brandPrimary}>
          <NativeTabs.Trigger name="index">
            <NativeTabs.Trigger.Icon sf="briefcase.fill" />
            <NativeTabs.Trigger.Label>Zawody</NativeTabs.Trigger.Label>
          </NativeTabs.Trigger>
          <NativeTabs.Trigger name="road">
            <NativeTabs.Trigger.Icon sf="map.fill" />
            <NativeTabs.Trigger.Label>Droga</NativeTabs.Trigger.Label>
          </NativeTabs.Trigger>
          <NativeTabs.Trigger name="profile">
            <NativeTabs.Trigger.Icon sf="person.fill" />
            <NativeTabs.Trigger.Label>Profil</NativeTabs.Trigger.Label>
          </NativeTabs.Trigger>
        </NativeTabs>
      </>
    );
  }

  return (
    <>
      <AiInfoModal />
      <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: colors.brandPrimary,
        tabBarInactiveTintColor: colors.muted,
        tabBarStyle: {
          backgroundColor: colors.surface,
          borderTopColor: colors.divider,
          ...(Platform.OS === "web" ? { height: 64 } : {}),
        },
        tabBarItemStyle: { alignSelf: "center" },
        tabBarLabelStyle: { fontFamily: fonts.semibold, fontSize: 12 },
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: "Zawody",
          tabBarButtonTestID: "tab-careers",
          tabBarIcon: ({ color, focused }) => <Ionicons name={focused ? "briefcase" : "briefcase-outline"} size={24} color={color} />,
        }}
      />
      <Tabs.Screen
        name="road"
        options={{
          title: "Droga",
          tabBarButtonTestID: "tab-road",
          tabBarIcon: ({ color, focused }) => <Ionicons name={focused ? "map" : "map-outline"} size={24} color={color} />,
        }}
      />
      <Tabs.Screen
        name="profile"
        options={{
          title: "Profil",
          tabBarButtonTestID: "tab-profile",
          tabBarIcon: ({ color, focused }) => <Ionicons name={focused ? "person" : "person-outline"} size={24} color={color} />,
        }}
      />
    </Tabs>
    </>
  );
}
