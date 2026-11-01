import { countryToLang, Lang } from "@/src/i18n/lang";
import { de } from "@/src/i18n/de";
import { en } from "@/src/i18n/en";
import { nl } from "@/src/i18n/nl";
import { pl } from "@/src/i18n/pl";
import { Strings } from "@/src/i18n/types";

export { countryToLang, Lang, Strings };

const dictionaries: Record<Lang, Strings> = { pl, en, de, nl };

export function getStrings(lang: Lang): Strings {
  return dictionaries[lang];
}
