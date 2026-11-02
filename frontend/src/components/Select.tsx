import { useState } from "react";
import { ActivityIndicator, ScrollView, Text, View } from "react-native";

import { Sheet } from "@/src/components/TaskSheet";
import { Ionicons, PressableScale, Txt } from "@/src/components/ui";
import { fonts, makeStyles, radius, spacing, useTheme } from "@/src/theme";

export type SelectOption = {
  code: string;
  flag?: string;
  label: string;
  subtitle?: string;
};

// A single-choice "dropdown" field: a compact row showing the current value which, on tap,
// opens a bottom sheet listing every option (flag + name + optional subtitle + selection mark).
// Replaces long vertical lists of individually-tappable cards so screens with many options
// (languages, countries) stay short and never overlap, regardless of label/flag length.
export function SelectField({
  testID,
  label,
  options,
  selectedCode,
  onSelect,
  loading,
  disabled,
}: {
  testID: string;
  label: string;
  options: SelectOption[];
  selectedCode: string;
  onSelect: (code: string) => void;
  loading?: boolean;
  disabled?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const styles = useSelectStyles();
  const { colors } = useTheme();
  const selected = options.find((o) => o.code === selectedCode) ?? options[0];

  return (
    <View style={{ gap: spacing.sm }}>
      <PressableScale
        testID={testID}
        disabled={disabled || loading}
        onPress={() => setOpen(true)}
        style={[styles.field, { opacity: disabled ? 0.6 : 1 }]}
      >
        {selected?.flag ? <Text style={styles.flag}>{selected.flag}</Text> : null}
        <View style={{ flex: 1 }}>
          <Text style={styles.value} numberOfLines={1}>
            {selected?.label}
          </Text>
          {selected?.subtitle ? (
            <Txt variant="caption" numberOfLines={1}>
              {selected.subtitle}
            </Txt>
          ) : null}
        </View>
        {loading ? (
          <ActivityIndicator color={colors.brandPrimary} size="small" />
        ) : (
          <Ionicons name="chevron-down" size={20} color={colors.muted} />
        )}
      </PressableScale>

      <Sheet visible={open} onClose={() => setOpen(false)} testID={`${testID}-sheet`}>
        <Txt variant="title" style={{ marginBottom: spacing.md }}>
          {label}
        </Txt>
        <ScrollView style={{ flexShrink: 1 }} showsVerticalScrollIndicator={false} contentContainerStyle={{ gap: spacing.sm, paddingBottom: spacing.sm }}>
          {options.map((o) => {
            const active = o.code === selectedCode;
            return (
              <PressableScale
                key={o.code}
                testID={`${testID}-option-${o.code}`}
                onPress={() => {
                  setOpen(false);
                  if (o.code !== selectedCode) onSelect(o.code);
                }}
                style={[styles.option, { borderColor: active ? colors.brandPrimary : colors.border }]}
              >
                {o.flag ? <Text style={styles.flag}>{o.flag}</Text> : null}
                <View style={{ flex: 1 }}>
                  <Text style={styles.value} numberOfLines={1}>
                    {o.label}
                  </Text>
                  {o.subtitle ? (
                    <Txt variant="caption" numberOfLines={1}>
                      {o.subtitle}
                    </Txt>
                  ) : null}
                </View>
                <Ionicons name={active ? "radio-button-on" : "radio-button-off"} size={22} color={active ? colors.brandPrimary : colors.borderStrong} />
              </PressableScale>
            );
          })}
        </ScrollView>
      </Sheet>
    </View>
  );
}

const useSelectStyles = makeStyles((c) => ({
  field: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    padding: spacing.md,
    borderRadius: radius.lg,
    borderWidth: 1.5,
    borderColor: c.border,
    backgroundColor: c.surfaceSecondary,
    minHeight: 60,
  },
  option: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    padding: spacing.md,
    borderRadius: radius.lg,
    borderWidth: 2,
    backgroundColor: c.surfaceSecondary,
    minHeight: 60,
  },
  flag: { fontSize: 26 },
  value: { fontFamily: fonts.bold, fontSize: 15, color: c.onSurface },
}));
