import { useQuery } from "@tanstack/react-query";
import { useRouter } from "expo-router";
import { useEffect, useRef, useState } from "react";
import { ActivityIndicator, FlatList, Pressable, ScrollView, Text, TextInput, View } from "react-native";
import { KeyboardAvoidingView } from "react-native-keyboard-controller";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, streamChat } from "@/src/api";
import { Button, IconButton, Ionicons, Txt } from "@/src/components/ui";
import { fonts, makeStyles, radius, spacing, useTheme } from "@/src/theme";

type Msg = { id: string; role: "user" | "assistant"; text: string };
type ChatData = { messages: Msg[]; remaining: number | null; limit: number; is_premium: boolean };

const SUGGESTIONS = [
  "Od czego zacząć w tym tygodniu?",
  "Jak napisać CV pod ten zawód?",
  "Jakie pytania padają na rozmowie?",
  "Czy mogę dostać kurs z urzędu pracy?",
  "Ile mogę zarabiać po roku?",
];

export default function Chat() {
  const insets = useSafeAreaInsets();
  const styles = useStyles();
  const { colors } = useTheme();
  const router = useRouter();
  const listRef = useRef<FlatList<Msg>>(null);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [remaining, setRemaining] = useState<number | null>(null);
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [limitHit, setLimitHit] = useState(false);

  const q = useQuery({ queryKey: ["chat"], queryFn: () => api<ChatData>("/chat"), staleTime: 0 });
  useEffect(() => {
    if (q.data) {
      setMsgs(q.data.messages.map((m) => ({ ...m, id: m.id || Math.random().toString() })));
      setRemaining(q.data.remaining);
      setLimitHit(q.data.remaining === 0);
    }
  }, [q.data]);

  const scrollEnd = () => setTimeout(() => listRef.current?.scrollToEnd({ animated: true }), 50);

  const send = async (raw?: string) => {
    const t = (raw ?? text).trim();
    if (!t || sending) return;
    setText("");
    setError("");
    setSending(true);
    const aid = `a${Date.now()}`;
    setMsgs((m) => [...m, { id: `u${Date.now()}`, role: "user", text: t }, { id: aid, role: "assistant", text: "" }]);
    scrollEnd();
    try {
      const res = await streamChat(t, (d) => {
        setMsgs((m) => m.map((x) => (x.id === aid ? { ...x, text: x.text + d } : x)));
        scrollEnd();
      });
      if (res.error) setError(res.error);
      setRemaining(res.remaining);
      if (res.remaining === 0) setLimitHit(true);
    } catch (e: any) {
      setMsgs((m) => m.filter((x) => x.id !== aid).slice(0, -1));
      if (e.status === 429) setLimitHit(true);
      setError(e.message);
      setText(t);
    } finally {
      setMsgs((m) => m.filter((x) => !(x.id === aid && !x.text)));
      setSending(false);
    }
  };

  const clear = async () => {
    await api("/chat", { method: "DELETE" });
    setMsgs([]);
  };

  return (
    <View style={styles.root}>
      <View style={[styles.header, { paddingTop: insets.top + spacing.sm }]}>
        <IconButton testID="chat-back-button" icon="arrow-back" onPress={() => (router.canGoBack() ? router.back() : router.replace("/(tabs)"))} />
        <View style={{ flex: 1 }}>
          <Txt variant="heading">Doradca kariery</Txt>
          <Txt variant="caption" testID="chat-remaining">
            {remaining === null ? "Premium · bez limitu" : `Darmowe pytania dziś: ${remaining}`}
          </Txt>
        </View>
        {msgs.length ? <IconButton testID="chat-clear-button" icon="trash-outline" onPress={clear} /> : null}
      </View>

      <KeyboardAvoidingView behavior="translate-with-padding" style={{ flex: 1 }}>
        {q.isLoading ? (
          <ActivityIndicator style={{ marginTop: spacing.xxl }} color={colors.brandPrimary} />
        ) : (
          <FlatList
            ref={listRef}
            testID="chat-list"
            data={msgs}
            keyExtractor={(m) => m.id}
            contentContainerStyle={{ padding: spacing.lg, gap: spacing.md, flexGrow: 1 }}
            onContentSizeChange={() => listRef.current?.scrollToEnd({ animated: false })}
            keyboardShouldPersistTaps="handled"
            ListEmptyComponent={
              <View style={styles.empty}>
                <View style={styles.emptyIcon}>
                  <Ionicons name="chatbubbles" size={34} color={colors.onBrandTertiary} />
                </View>
                <Txt variant="title" style={{ textAlign: "center" }}>
                  O co chcesz zapytać?
                </Txt>
                <Txt style={{ textAlign: "center" }}>Doradca zna Twoje odpowiedzi z ankiety i wybraną ścieżkę kariery.</Txt>
              </View>
            }
            renderItem={({ item }) => (
              <View style={[styles.bubble, item.role === "user" ? styles.userBubble : styles.aiBubble]} testID={`chat-msg-${item.role}`}>
                {item.text ? (
                  <Text style={[styles.msgText, item.role === "user" && { color: colors.onBrandPrimary }]}>{item.text.replace(/\*\*|^#+\s/gm, "")}</Text>
                ) : (
                  <ActivityIndicator color={colors.brandPrimary} size="small" />
                )}
              </View>
            )}
          />
        )}

        {limitHit ? (
          <View style={styles.limit} testID="chat-limit">
            <Txt variant="label">Wykorzystano darmowe pytania na dziś</Txt>
            <Txt variant="caption">Wróć jutro albo odblokuj nielimitowane rozmowy w Premium.</Txt>
            <Button testID="chat-go-premium" title="Zobacz Premium" icon="diamond" onPress={() => router.push("/premium")} />
          </View>
        ) : (
          <>
            {!msgs.length ? (
              <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.sugRow} contentContainerStyle={styles.sugContent}>
                {SUGGESTIONS.map((s, i) => (
                  <Pressable key={s} testID={`chat-suggestion-${i}`} onPress={() => send(s)} style={styles.sug}>
                    <Text style={styles.sugText}>{s}</Text>
                  </Pressable>
                ))}
              </ScrollView>
            ) : null}
            {error ? (
              <Text style={styles.error} testID="chat-error">
                {error}
              </Text>
            ) : null}
            <View style={[styles.inputBar, { paddingBottom: insets.bottom + spacing.sm }]}>
              <TextInput
                testID="chat-input"
                value={text}
                onChangeText={setText}
                placeholder="Napisz pytanie…"
                placeholderTextColor={colors.muted}
                multiline
                style={styles.input}
              />
              <Pressable
                testID="chat-send-button"
                onPress={() => send()}
                disabled={!text.trim() || sending}
                style={[styles.send, { opacity: !text.trim() || sending ? 0.5 : 1 }]}
              >
                {sending ? <ActivityIndicator color={colors.onBrandPrimary} /> : <Ionicons name="arrow-up" size={22} color={colors.onBrandPrimary} />}
              </Pressable>
            </View>
          </>
        )}
      </KeyboardAvoidingView>
    </View>
  );
}

const useStyles = makeStyles((c) => ({
  root: { flex: 1, backgroundColor: c.surface },
  header: { flexDirection: "row", alignItems: "center", gap: spacing.md, paddingHorizontal: spacing.lg, paddingBottom: spacing.md, borderBottomWidth: 1, borderBottomColor: c.divider },
  empty: { flex: 1, alignItems: "center", justifyContent: "center", gap: spacing.md, padding: spacing.xl },
  emptyIcon: { width: 72, height: 72, borderRadius: 36, backgroundColor: c.brandTertiary, alignItems: "center", justifyContent: "center" },
  bubble: { maxWidth: "86%", borderRadius: radius.lg, paddingHorizontal: spacing.lg, paddingVertical: spacing.md },
  userBubble: { alignSelf: "flex-end", backgroundColor: c.brandPrimary, borderBottomRightRadius: radius.sm },
  aiBubble: { alignSelf: "flex-start", backgroundColor: c.surfaceSecondary, borderBottomLeftRadius: radius.sm, borderWidth: 1, borderColor: c.border },
  msgText: { fontFamily: fonts.regular, fontSize: 15, lineHeight: 22, color: c.onSurface },
  sugRow: { flexGrow: 0, height: 56 },
  sugContent: { paddingHorizontal: spacing.lg, gap: spacing.sm, alignItems: "center" },
  sug: { height: 36, paddingHorizontal: spacing.md, borderRadius: radius.pill, backgroundColor: c.brandTertiary, justifyContent: "center", flexShrink: 0 },
  sugText: { fontFamily: fonts.semibold, fontSize: 13, color: c.onBrandTertiary },
  error: { fontFamily: fonts.medium, fontSize: 13, color: c.error, paddingHorizontal: spacing.lg, paddingBottom: spacing.xs },
  inputBar: { flexDirection: "row", alignItems: "flex-end", gap: spacing.sm, paddingHorizontal: spacing.lg, paddingTop: spacing.sm, borderTopWidth: 1, borderTopColor: c.divider, backgroundColor: c.surface },
  input: {
    flex: 1,
    minHeight: 48,
    maxHeight: 120,
    borderRadius: radius.lg,
    backgroundColor: c.surfaceSecondary,
    borderWidth: 1,
    borderColor: c.border,
    paddingHorizontal: spacing.lg,
    paddingTop: 13,
    paddingBottom: 13,
    fontFamily: fonts.medium,
    fontSize: 15,
    color: c.onSurface,
  },
  send: { width: 48, height: 48, borderRadius: 24, backgroundColor: c.brandPrimary, alignItems: "center", justifyContent: "center" },
  limit: { margin: spacing.lg, marginBottom: 0, padding: spacing.lg, gap: spacing.sm, borderRadius: radius.lg, backgroundColor: c.brandTertiary, paddingBottom: spacing.lg },
}));
