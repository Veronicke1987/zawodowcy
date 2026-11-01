import { Lang } from "@/src/i18n/lang";

// Shared list of supported countries/markets — used both on the pre-login country picker
// and on the Profile screen's "Kraj i rynek pracy" selector. Keep in sync with backend
// COUNTRY_CONFIG keys (PL, US, GB, AU, DE, NL).
export type CountryOption = { code: string; flag: string; name: string; lang: string; names: Record<Lang, string>; langNames: Record<Lang, string> };

export const COUNTRIES: CountryOption[] = [
  {
    code: "PL", flag: "🇵🇱", name: "Polska", lang: "polski",
    names: { pl: "Polska", en: "Poland", de: "Polen", nl: "Polen" },
    langNames: { pl: "polskim", en: "Polish", de: "Polnisch", nl: "Pools" },
  },
  {
    code: "US", flag: "🇺🇸", name: "USA", lang: "angielski",
    names: { pl: "USA", en: "USA", de: "USA", nl: "VS" },
    langNames: { pl: "angielskim", en: "English", de: "Englisch", nl: "Engels" },
  },
  {
    code: "GB", flag: "🇬🇧", name: "Wielka Brytania", lang: "angielski",
    names: { pl: "Wielka Brytania", en: "United Kingdom", de: "Vereinigtes Königreich", nl: "Verenigd Koninkrijk" },
    langNames: { pl: "angielskim", en: "English", de: "Englisch", nl: "Engels" },
  },
  {
    code: "AU", flag: "🇦🇺", name: "Australia", lang: "angielski",
    names: { pl: "Australia", en: "Australia", de: "Australien", nl: "Australië" },
    langNames: { pl: "angielskim", en: "English", de: "Englisch", nl: "Engels" },
  },
  {
    code: "DE", flag: "🇩🇪", name: "Niemcy", lang: "niemiecki",
    names: { pl: "Niemcy", en: "Germany", de: "Deutschland", nl: "Duitsland" },
    langNames: { pl: "niemieckim", en: "German", de: "Deutsch", nl: "Duits" },
  },
  {
    code: "NL", flag: "🇳🇱", name: "Holandia", lang: "niderlandzki",
    names: { pl: "Holandia", en: "Netherlands", de: "Niederlande", nl: "Nederland" },
    langNames: { pl: "niderlandzkim", en: "Dutch", de: "Niederländisch", nl: "Nederlands" },
  },
];

export const LOCAL_COUNTRY_KEY = "local_country";
