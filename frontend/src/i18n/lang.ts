// Maps a country/market code to the UI language the app should render in.
// The country is chosen once, before login (and remembered locally), or taken
// from the logged-in user's profile afterwards — see src/auth.tsx.
export type Lang = "pl" | "en" | "de" | "nl";

export function countryToLang(country?: string | null): Lang {
  switch ((country || "PL").toUpperCase()) {
    case "DE":
      return "de";
    case "NL":
      return "nl";
    case "US":
    case "GB":
    case "AU":
      return "en";
    default:
      return "pl";
  }
}
