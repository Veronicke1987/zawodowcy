// In-app Google Play / App Store rating prompt.
//
// Native-only (requires a real device build via the store, not Expo Go/web) — on web and
// Expo Go `StoreReview.isAvailableAsync()` simply resolves false, so this silently no-ops there.
//
// Rules to avoid annoying the user:
// - Each "trigger" (a positive moment in the app) only ever fires ONCE per device, ever.
// - We additionally cap the TOTAL number of prompts shown across all triggers combined,
//   and enforce a cooldown between any two prompts — so even a user who hits several
//   positive moments close together only sees this a couple of times, spaced out.
import * as StoreReview from "expo-store-review";

import { storage } from "@/src/utils/storage";

const MAX_TOTAL_PROMPTS = 2;
const MIN_GAP_DAYS = 45;
const MIN_GAP_MS = MIN_GAP_DAYS * 24 * 60 * 60 * 1000;

async function withinCooldown(): Promise<boolean> {
  const count = (await storage.getItem<number>("review_prompt_count", 0)) ?? 0;
  if (count >= MAX_TOTAL_PROMPTS) return true;
  const lastAt = (await storage.getItem<number>("review_prompt_last_at", 0)) ?? 0;
  if (lastAt && Date.now() - lastAt < MIN_GAP_MS) return true;
  return false;
}

// triggerKey examples: "first_roadmap", "path_complete", "streak_7".
export async function maybeRequestReview(triggerKey: string): Promise<void> {
  const firedKey = `review_fired_${triggerKey}`;
  const alreadyFired = (await storage.getItem<boolean>(firedKey, false)) ?? false;
  if (alreadyFired) return;
  await storage.setItem(firedKey, true); // mark this specific moment as used regardless of outcome below

  if (await withinCooldown()) return;
  try {
    const available = await StoreReview.isAvailableAsync();
    if (!available) return;
    await StoreReview.requestReview();
    const count = (await storage.getItem<number>("review_prompt_count", 0)) ?? 0;
    await storage.setItem("review_prompt_count", count + 1);
    await storage.setItem("review_prompt_last_at", Date.now());
  } catch {
    // requestReview is a best-effort native call; never let it break the calling flow.
  }
}
