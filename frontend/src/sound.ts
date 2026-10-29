import { createAudioPlayer, setAudioModeAsync } from "expo-audio";
import * as Haptics from "expo-haptics";

let player: ReturnType<typeof createAudioPlayer> | null = null;

export async function playSuccess() {
  Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success).catch(() => {});
  try {
    await setAudioModeAsync({ playsInSilentMode: true });
    if (!player) player = createAudioPlayer(require("../assets/sounds/success.wav"));
    await player.seekTo(0);
    player.play();
  } catch {
    // sound is a bonus; never block the flow
  }
}
