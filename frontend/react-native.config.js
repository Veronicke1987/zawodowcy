module.exports = {
  dependencies: {
    // TEMPORARILY excluded from native autolinking while diagnosing a crash-on-launch reported
    // on real Play Store installs (app shows the splash screen then force-closes ~1s later).
    // Removing the Expo config plugin entry in app.json ONLY skips injecting the AdMob App ID
    // into AndroidManifest/Info.plist — it does NOT stop the native module from being autolinked
    // (autolinking is driven by package.json dependencies, independent of the Expo "plugins"
    // array), so without this override the native AdMob SDK would still compile in but WITHOUT
    // its required App ID metadata, which is a known, documented Android crash cause — i.e. worse
    // than doing nothing. This override fully excludes the module from both platforms' native
    // builds so the next Play Store build can be used to confirm/rule out AdMob as the cause.
    // All JS call sites (src/ads/ads.ts, src/ads/AdsProvider.tsx) already handle the native module
    // being absent gracefully (adsAvailable=false -> ads are simply skipped).
    // RE-ENABLE by deleting this whole file once the crash is confirmed fixed/unrelated, and
    // restore the "react-native-google-mobile-ads" plugin block in app.json (see git history).
    "react-native-google-mobile-ads": {
      platforms: {
        android: null,
        ios: null,
      },
    },
  },
};
