// Web preview: no AdMob. The app shows a simulated ad instead.
export const adsAvailable = false;
export async function initAds() {}
export async function showRewarded(): Promise<boolean> {
  return false;
}
export async function showInterstitial(): Promise<void> {}
