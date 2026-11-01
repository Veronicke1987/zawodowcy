import { useEffect, useState } from "react";
import { Modal, View } from "react-native";

import { useAds } from "@/src/ads/AdsProvider";
import { api } from "@/src/api";
import { useAuth } from "@/src/auth";
import { Button, Ionicons, PressableScale, Txt } from "@/src/components/ui";
import { maybeRequestReview } from "@/src/review";
import { playSuccess } from "@/src/sound";
import { makeStyles, radius, spacing, useTheme } from "@/src/theme";

// Compact badge for headers — shows the current login streak, or a dimmed
// flame when yesterday was missed and the streak can still be restored today.
export function StreakBadge({ testID }: { testID?: string }) {
  const { user } = useAuth();
  const { colors } = useTheme();
  const styles = useStyles();
  const [open, setOpen] = useState(false);
  const streak = user?.streak;
  // A 7-day streak is a strong "I actually use this app" signal — a good, low-friction
  // moment to ask for a rating (fires once ever, see src/review.ts).
  useEffect(() => {
    if (streak && !streak.pending_restore && streak.count >= 7) maybeRequestReview("streak_7");
  }, [streak]);
  if (!streak) return null;
  const broken = streak.pending_restore;

  return (
    <>
      <PressableScale testID={testID ?? "streak-badge"} onPress={() => setOpen(true)} style={[styles.badge, broken && styles.badgeBroken]}>
        <Ionicons name={broken ? "flame-outline" : "flame"} size={16} color={broken ? colors.muted : "#FF8A00"} />
        <Txt variant="label" style={broken ? { color: colors.muted } : undefined}>
          {broken ? "0" : streak.count}
        </Txt>
      </PressableScale>
      <StreakModal visible={open} onClose={() => setOpen(false)} />
    </>
  );
}

export function StreakCard({ testID }: { testID?: string }) {
  const { user, t } = useAuth();
  const { colors } = useTheme();
  const styles = useStyles();
  const [open, setOpen] = useState(false);
  const streak = user?.streak;
  if (!streak) return null;
  const broken = streak.pending_restore;

  return (
    <>
      <PressableScale testID={testID ?? "streak-card"} onPress={() => setOpen(true)} style={styles.card}>
        <View style={[styles.cardIcon, broken && { backgroundColor: colors.surfaceSecondary }]}>
          <Ionicons name={broken ? "flame-outline" : "flame"} size={24} color={broken ? colors.muted : "#FF8A00"} />
        </View>
        <View style={{ flex: 1 }}>
          <Txt variant="heading">{broken ? t.streak.lostCardTitle : t.streak.activeTitle(streak.count)}</Txt>
          <Txt variant="caption">{broken ? t.streak.lostCardSub : t.streak.activeText(streak.best)}</Txt>
        </View>
        <Ionicons name="chevron-forward" size={18} color={colors.muted} />
      </PressableScale>
      <StreakModal visible={open} onClose={() => setOpen(false)} />
    </>
  );
}

function StreakModal({ visible, onClose }: { visible: boolean; onClose: () => void }) {
  const { user, refresh, t } = useAuth();
  const { watchAd } = useAds();
  const { colors } = useTheme();
  const styles = useStyles();
  const [restoring, setRestoring] = useState(false);
  const [error, setError] = useState("");
  const streak = user?.streak;

  const restore = async () => {
    setError("");
    setRestoring(true);
    try {
      if (!(await watchAd(t.ads.reasonRestoreStreak))) return;
      await api("/streak/restore", { method: "POST" });
      playSuccess();
      await refresh();
      onClose();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setRestoring(false);
    }
  };

  if (!streak) return null;

  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
      <PressableScale testID="streak-modal-backdrop" haptic={false} onPress={onClose} style={styles.backdrop}>
        <PressableScale haptic={false} onPress={() => {}} style={styles.sheet} testID="streak-modal">
          {streak.pending_restore ? (
            <>
              <Ionicons name="flame-outline" size={40} color={colors.muted} />
              <Txt variant="title" style={{ textAlign: "center" }}>
                {t.streak.lostTitle(streak.lost_count)}
              </Txt>
              <Txt style={{ textAlign: "center" }}>{t.streak.lostText}</Txt>
              {error ? (
                <Txt style={{ color: colors.error, textAlign: "center" }} testID="streak-restore-error">
                  {error}
                </Txt>
              ) : null}
              <Button testID="streak-restore-button" title={t.streak.restoreButton} icon="play" onPress={restore} loading={restoring} />
              <Button testID="streak-dismiss-button" title={t.streak.restartButton} variant="ghost" onPress={onClose} />
            </>
          ) : (
            <>
              <Ionicons name="flame" size={40} color="#FF8A00" />
              <Txt variant="title" style={{ textAlign: "center" }}>
                {t.streak.activeTitle(streak.count)}
              </Txt>
              <Txt style={{ textAlign: "center" }}>{t.streak.activeText(streak.best)}</Txt>
              <Button testID="streak-close-button" title={t.streak.closeButton} onPress={onClose} />
            </>
          )}
        </PressableScale>
      </PressableScale>
    </Modal>
  );
}

const useStyles = makeStyles((c) => ({
  badge: { flexDirection: "row", alignItems: "center", gap: 4, paddingHorizontal: spacing.sm, paddingVertical: 6, borderRadius: radius.pill, backgroundColor: c.surfaceSecondary },
  badgeBroken: { opacity: 0.8 },
  card: { flexDirection: "row", alignItems: "center", gap: spacing.md, padding: spacing.lg, borderRadius: radius.lg, backgroundColor: c.surfaceSecondary },
  cardIcon: { width: 44, height: 44, borderRadius: 22, backgroundColor: "#FF8A0022", alignItems: "center", justifyContent: "center" },
  backdrop: { flex: 1, backgroundColor: "rgba(0,0,0,0.5)", alignItems: "center", justifyContent: "center", padding: spacing.xl },
  sheet: { backgroundColor: c.surface, borderRadius: radius.lg, padding: spacing.xl, gap: spacing.md, alignItems: "center", width: "100%", maxWidth: 360 },
}));
