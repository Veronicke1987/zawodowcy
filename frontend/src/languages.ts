import { Lang } from "@/src/i18n/lang";

// Interface language — fully independent from the job-search country (see src/countries.ts).
// Shown both on the pre-login country-select screen and in Profile settings. Keep in sync with
// the backend's SUPPORTED_LANGUAGES and the 4 dictionaries under src/i18n/*.ts.
export type LanguageOption = { code: Lang; flag: string; nativeName: string };

export const UI_LANGUAGES: LanguageOption[] = [
  { code: "pl", flag: "🇵🇱", nativeName: "Polski" },
  { code: "en", flag: "🇬🇧", nativeName: "English" },
  { code: "de", flag: "🇩🇪", nativeName: "Deutsch" },
  { code: "nl", flag: "🇳🇱", nativeName: "Nederlands" },
];

export const LOCAL_LANGUAGE_KEY = "local_language";
