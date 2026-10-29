import { useMemo, useState } from "react";
import { Pressable, Text, View } from "react-native";
import Animated, { FadeIn } from "react-native-reanimated";
import Svg, { Circle, Path } from "react-native-svg";

import { Milestone, Task } from "@/src/api";
import { Ionicons } from "@/src/components/ui";
import { fonts, makeStyles, radius, spacing, useTheme } from "@/src/theme";

type Item =
  | { kind: "start"; done: true }
  | { kind: "task"; task: Task; done: boolean }
  | { kind: "milestone"; milestone: Milestone; index: number; done: boolean; current: boolean; last: boolean };

const H = { start: 90, task: 78, milestone: 128 };

export function milestoneDone(m: Milestone) {
  return m.tasks.length > 0 && m.tasks.every((t) => t.done);
}

export function RoadMap({
  milestones,
  onTask,
  onMilestone,
}: {
  milestones: Milestone[];
  onTask: (t: Task) => void;
  onMilestone: (m: Milestone, i: number) => void;
}) {
  const { colors } = useTheme();
  const styles = useStyles();
  const [width, setWidth] = useState(0);

  const items: Item[] = useMemo(() => {
    const out: Item[] = [{ kind: "start", done: true }];
    const currentIdx = milestones.findIndex((m) => !milestoneDone(m));
    milestones.forEach((m, i) => {
      m.tasks.forEach((t) => out.push({ kind: "task", task: t, done: t.done }));
      out.push({ kind: "milestone", milestone: m, index: i, done: milestoneDone(m), current: i === currentIdx, last: i === milestones.length - 1 });
    });
    return out;
  }, [milestones]);

  const points = useMemo(() => {
    let y = 24;
    const amp = width * 0.2;
    return items.map((it, i) => {
      const h = H[it.kind];
      const p = { x: width / 2 + amp * Math.sin(i * 0.85), y: y + h / 2, h };
      y += h;
      return p;
    });
  }, [items, width]);

  const totalH = points.length ? points[points.length - 1].y + points[points.length - 1].h / 2 + 24 : 0;

  const seg = (i: number) => {
    const p0 = points[Math.max(i - 1, 0)];
    const p1 = points[i];
    const p2 = points[i + 1];
    const p3 = points[Math.min(i + 2, points.length - 1)];
    const c1x = p1.x + (p2.x - p0.x) / 6;
    const c1y = p1.y + (p2.y - p0.y) / 6;
    const c2x = p2.x - (p3.x - p1.x) / 6;
    const c2y = p2.y - (p3.y - p1.y) / 6;
    return `M ${p1.x} ${p1.y} C ${c1x} ${c1y}, ${c2x} ${c2y}, ${p2.x} ${p2.y}`;
  };

  return (
    <View onLayout={(e) => setWidth(e.nativeEvent.layout.width)} style={{ height: totalH || 400 }} testID="roadmap-road">
      {width > 0 ? (
        <>
          <Svg width={width} height={totalH} style={{ position: "absolute" }}>
            {points.slice(0, -1).map((_, i) => (
              <Path key={`b${i}`} d={seg(i)} stroke={colors.borderStrong} strokeWidth={36} strokeLinecap="round" fill="none" />
            ))}
            {points.slice(0, -1).map((_, i) => (
              <Path key={`r${i}`} d={seg(i)} stroke={colors.surfaceTertiary} strokeWidth={30} strokeLinecap="round" fill="none" />
            ))}
            {points.slice(0, -1).map((_, i) =>
              items[i + 1].done ? (
                <Path key={`c${i}`} d={seg(i)} stroke={colors.brandPrimary} strokeWidth={6} strokeLinecap="round" fill="none" />
              ) : (
                <Path key={`c${i}`} d={seg(i)} stroke={colors.surface} strokeWidth={3} strokeDasharray="10,10" fill="none" />
              ),
            )}
            {points.length ? <Circle cx={points[0].x} cy={points[0].y} r={6} fill={colors.brandPrimary} /> : null}
          </Svg>
          {items.map((it, i) => {
            const p = points[i];
            const leftSide = p.x > width / 2;
            const nodeR = it.kind === "milestone" ? 32 : it.kind === "task" ? 18 : 22;
            const labelStyle = leftSide
              ? { left: spacing.md, width: p.x - nodeR - spacing.md * 2, alignItems: "flex-end" as const }
              : { left: p.x + nodeR + spacing.md, width: width - p.x - nodeR - spacing.md * 2 };
            return (
              <Animated.View key={i} entering={FadeIn.delay(i * 40)} style={[styles.abs, { top: p.y - p.h / 2, height: p.h, width }]} pointerEvents="box-none">
                {it.kind === "start" ? (
                  <>
                    <View style={[styles.node, { left: p.x - nodeR, top: p.h / 2 - nodeR, width: nodeR * 2, height: nodeR * 2, backgroundColor: colors.surfaceInverse }]}>
                      <Ionicons name="location" size={22} color={colors.onSurfaceInverse} />
                    </View>
                    <View style={[styles.label, labelStyle, { top: p.h / 2 - 22 }]}>
                      <Text style={styles.lblTitle}>Start</Text>
                      <Text style={styles.lblSub}>Tu jesteś dziś</Text>
                    </View>
                  </>
                ) : it.kind === "task" ? (
                  <>
                    <Pressable
                      testID={`road-task-${it.task.id}`}
                      onPress={() => onTask(it.task)}
                      hitSlop={6}
                      style={[
                        styles.node,
                        {
                          left: p.x - nodeR,
                          top: p.h / 2 - nodeR,
                          width: nodeR * 2,
                          height: nodeR * 2,
                          backgroundColor: it.done ? colors.brandPrimary : colors.surface,
                          borderWidth: it.done ? 0 : 3,
                          borderColor: colors.borderStrong,
                        },
                      ]}
                    >
                      {it.done ? <Ionicons name="checkmark" size={20} color={colors.onBrandPrimary} /> : null}
                    </Pressable>
                    <Pressable onPress={() => onTask(it.task)} style={[styles.label, styles.taskLabel, labelStyle, { top: p.h / 2 - 26 }]}>
                      <Text numberOfLines={2} style={[styles.taskText, it.done && { color: colors.muted, textDecorationLine: "line-through" }, leftSide && { textAlign: "right" }]}>
                        {it.task.title}
                      </Text>
                    </Pressable>
                  </>
                ) : (
                  <>
                    <Pressable
                      testID={`road-milestone-${it.index}`}
                      onPress={() => onMilestone(it.milestone, it.index)}
                      style={[
                        styles.node,
                        styles.bigNode,
                        {
                          left: p.x - nodeR,
                          top: p.h / 2 - nodeR,
                          width: nodeR * 2,
                          height: nodeR * 2,
                          backgroundColor: it.done ? colors.success : it.current ? colors.brandPrimary : colors.surfaceSecondary,
                          borderColor: it.current ? colors.brandTertiary : colors.surface,
                        },
                      ]}
                    >
                      <Ionicons
                        name={it.done ? "checkmark-done" : it.last ? "trophy" : "briefcase"}
                        size={26}
                        color={it.done ? colors.onSuccess : it.current ? colors.onBrandPrimary : colors.muted}
                      />
                    </Pressable>
                    <Pressable onPress={() => onMilestone(it.milestone, it.index)} style={[styles.label, styles.card, labelStyle, { top: p.h / 2 - 44 }]}>
                      <Text style={styles.level}>{it.last ? "CEL" : `POZIOM ${it.index + 1}`}</Text>
                      <Text numberOfLines={2} style={[styles.lblTitle, leftSide && { textAlign: "right" }]}>
                        {it.milestone.title}
                      </Text>
                      <Text style={styles.lblSub}>
                        {it.milestone.tasks.filter((t) => t.done).length}/{it.milestone.tasks.length} zdobyte
                      </Text>
                    </Pressable>
                  </>
                )}
              </Animated.View>
            );
          })}
        </>
      ) : null}
    </View>
  );
}

const useStyles = makeStyles((c) => ({
  abs: { position: "absolute", left: 0 },
  node: { position: "absolute", borderRadius: 999, alignItems: "center", justifyContent: "center" },
  bigNode: { borderWidth: 4, shadowColor: "#000", shadowOpacity: 0.15, shadowRadius: 8, shadowOffset: { width: 0, height: 4 }, elevation: 4 },
  label: { position: "absolute" },
  taskLabel: { backgroundColor: c.surface, borderRadius: radius.sm, paddingHorizontal: 6, paddingVertical: 4, minHeight: 44, justifyContent: "center" },
  card: {
    backgroundColor: c.surfaceSecondary,
    borderRadius: radius.md,
    padding: spacing.sm,
    paddingHorizontal: spacing.md,
    borderWidth: 1,
    borderColor: c.border,
  },
  level: { fontFamily: fonts.bold, fontSize: 10, letterSpacing: 1, color: c.brandPrimary },
  lblTitle: { fontFamily: fonts.bold, fontSize: 14, lineHeight: 18, color: c.onSurface },
  lblSub: { fontFamily: fonts.medium, fontSize: 11, color: c.muted },
  taskText: { fontFamily: fonts.semibold, fontSize: 13, lineHeight: 17, color: c.onSurfaceSecondary },
}));
