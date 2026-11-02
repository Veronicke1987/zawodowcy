// Native: real AdMob ads in a development/production build. Expo Go has no native
// AdMob module, so the guarded require fails closed and the app shows a simulated ad.
//
// TEMPORARILY DISABLED (see app.json — the "react-native-google-mobile-ads" config plugin
// was removed) while diagnosing a crash-on-launch reported on real Play Store installs:
// removing the plugin means the native module is no longer linked into the build at all, so
// the require() below will fail and `adsAvailable` will be false everywhere — ads are simply
// skipped, nothing else needs to change. Once the crash is confirmed fixed/unrelated, restore
// the plugin block in app.json (see its git history) to bring real ads back.
import Constants from "expo-constants";

let sdk: any = null;
try {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  if (Constants.executionEnvironment !== "storeClient") sdk = require("react-native-google-mobile-ads");
} catch (error) {
  console.log("[ads] react-native-google-mobile-ads unavailable, falling back to simulated ads:", error);
  sdk = null;
}

export const adsAvailable = Boolean(sdk?.RewardedAd && sdk?.InterstitialAd);

const REWARDED_ID = process.env.EXPO_PUBLIC_ADMOB_REWARDED_ID || sdk?.TestIds?.REWARDED;
const INTERSTITIAL_ID = process.env.EXPO_PUBLIC_ADMOB_INTERSTITIAL_ID || sdk?.TestIds?.INTERSTITIAL;

let started = false;
export async function initAds() {
  if (!adsAvailable || started) return;
  started = true;
  try {
    await sdk.default().initialize();
  } catch (error) {
    // Missing/placeholder production App ID, no network, etc. — ads just stay off, never crash.
    console.log("[ads] initialize() failed, ads stay disabled for this session:", error);
  }
}

// Resolves true only when the user earned the reward.
export function showRewarded(): Promise<boolean> {
  if (!adsAvailable) return Promise.resolve(false);
  const ad = sdk.RewardedAd.createForAdRequest(REWARDED_ID);
  return new Promise((resolve) => {
    let earned = false;
    const offs: (() => void)[] = [];
    const done = (v: boolean) => {
      offs.forEach((o) => o());
      resolve(v);
    };
    offs.push(ad.addAdEventListener(sdk.RewardedAdEventType.LOADED, () => ad.show().catch(() => done(false))));
    offs.push(ad.addAdEventListener(sdk.RewardedAdEventType.EARNED_REWARD, () => (earned = true)));
    offs.push(ad.addAdEventListener(sdk.AdEventType.CLOSED, () => done(earned)));
    offs.push(ad.addAdEventListener(sdk.AdEventType.ERROR, () => done(false)));
    ad.load();
  });
}

export function showInterstitial(): Promise<void> {
  if (!adsAvailable) return Promise.resolve();
  const ad = sdk.InterstitialAd.createForAdRequest(INTERSTITIAL_ID);
  return new Promise((resolve) => {
    const offs: (() => void)[] = [];
    const done = () => {
      offs.forEach((o) => o());
      resolve();
    };
    offs.push(ad.addAdEventListener(sdk.AdEventType.LOADED, () => ad.show().catch(done)));
    offs.push(ad.addAdEventListener(sdk.AdEventType.CLOSED, done));
    offs.push(ad.addAdEventListener(sdk.AdEventType.ERROR, done));
    ad.load();
  });
}
