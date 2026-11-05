// Native: real AdMob ads in a development/production build. Expo Go has no native
// AdMob module, so the guarded require fails closed and the app shows a simulated ad.
//
// RE-ENABLED: the "react-native-google-mobile-ads" config plugin is back in app.json,
// using Google's public TEST App IDs for now (zero revenue, but never fails Play Store
// review). The production crash-on-launch was caused by two missing native-build pieces,
// both now fixed in app.json: the AD_ID permission (required on Android 13+/API 33+ for
// any app that reads the Advertising ID) and ProGuard keep-rules for the Google Mobile Ads
// SDK (release builds minify/strip classes that debug builds don't, which is why it only
// crashed on real Play Store installs and never in development). See expo-build-properties
// plugin entry for the ProGuard rules. Swap in real AdMob App IDs / Ad Unit IDs once a live
// AdMob account is ready — no other code changes needed, see EXPO_PUBLIC_ADMOB_* below.
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
