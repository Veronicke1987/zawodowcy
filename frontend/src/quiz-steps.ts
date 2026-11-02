import { Lang } from "@/src/i18n/lang";

export type CardOption = { value: string; label: string; desc: string; icon: string };

export type Group = {
  key: string;
  label?: string;
  type: "single" | "multi" | "text" | "traits" | "cards";
  options?: string[];
  cards?: CardOption[];
  placeholder?: string;
  multiline?: boolean;
  required?: boolean;
  traits?: { key: string; left: string; right: string }[];
};

export type QuizStep = { title: string; subtitle: string; groups: Group[]; showIf?: (a: Record<string, any>) => boolean };

export const RESET_MODES: Record<string, { label: string; short: string }> = {
  search: { label: "Szukam swojej drogi", short: "SZUKAM SWOJEJ DROGI" },
  industry: { label: "Zmiana branży", short: "ZMIANA BRANŻY" },
  life: { label: "Nowy Rozdział", short: "NOWY ROZDZIAŁ · ZMIANA ŻYCIA" },
};

const isLife = (a: Record<string, any>) => a.reset_mode === "life";
const isIndustry = (a: Record<string, any>) => a.reset_mode === "industry";

export const QUIZ_STEPS: QuizStep[] = [
  {
    title: "Jakiej zmiany szukasz?",
    subtitle: "Wybierz, jak dużej zmiany szukasz — dopasujemy do tego pytania i propozycje.",
    groups: [
      {
        key: "reset_mode",
        type: "cards",
        required: true,
        cards: [
          {
            value: "search",
            label: "Szukam swojej drogi",
            desc: "Chcę znaleźć pracę, która pasuje do tego, co już umiem i lubię.",
            icon: "compass",
          },
          {
            value: "industry",
            label: "Zmieniam branżę",
            desc: "Wykorzystam swoje umiejętności, ale w zupełnie innej branży.",
            icon: "swap-horizontal",
          },
          {
            value: "life",
            label: "Nowy Rozdział — zmieniam życie",
            desc: "Zaczynam od nowa: inne obowiązki, inny rytm dnia, coś, co naprawdę mnie kręci.",
            icon: "rocket",
          },
        ],
      },
    ],
  },
  {
    title: "Co robisz obecnie?",
    subtitle: "Zacznijmy od Twojej sytuacji — nie ma złych odpowiedzi.",
    groups: [
      {
        key: "current_status",
        type: "single",
        required: true,
        options: [
          "Pracuję i chcę zmienić zawód",
          "Straciłem/am pracę przez AI lub automatyzację",
          "Szukam pracy",
          "Uczę się / studiuję",
          "Dopiero wybieram drogę",
          "Prowadzę firmę",
          "Wracam na rynek pracy",
        ],
      },
      { key: "current_job", label: "Obecne lub ostatnie stanowisko i branża", type: "text", placeholder: "np. kasjerka w markecie, 5 lat" },
    ],
  },
  {
    title: "Masz już coś na myśli?",
    subtitle: "Każdy nowy rozdział zaczyna się od marzenia — nawet jeśli jest jeszcze mgliste.",
    showIf: isLife,
    groups: [
      {
        key: "has_idea",
        type: "single",
        required: true,
        options: ["Tak, wiem, czego chcę", "Mam kilka luźnych pomysłów", "Nie, zaskoczcie mnie!"],
      },
      {
        key: "idea",
        label: "Opisz swój pomysł lub marzenie",
        type: "text",
        multiline: true,
        placeholder: "np. chciałabym pracować ze zwierzętami, otworzyć małą kawiarnię, uczyć jogi…",
      },
    ],
  },
  {
    title: "Jakie kierunki Cię kuszą?",
    subtitle: "Zaznacz wszystko, co brzmi jak nowe, lepsze życie.",
    showIf: isLife,
    groups: [
      {
        key: "new_directions",
        type: "multi",
        required: true,
        options: [
          "Praca z ludźmi i pomaganie",
          "Praca twórcza",
          "Praca na świeżym powietrzu",
          "Rękodzieło i rzemiosło",
          "Technologia i internet",
          "Własny biznes",
          "Praca zdalna z dowolnego miejsca",
          "Podróże i praca za granicą",
          "Zdrowie, sport i wellbeing",
          "Zwierzęta i natura",
          "Edukacja i szkolenia",
          "Kulinaria",
        ],
      },
    ],
  },
  {
    title: "Co kochasz robić?",
    subtitle: "Twoje pasje to najlepsza wskazówka, dokąd iść.",
    showIf: isLife,
    groups: [
      {
        key: "loves",
        label: "Przy czym tracisz poczucie czasu?",
        type: "text",
        multiline: true,
        placeholder: "np. gotowanie dla znajomych, majsterkowanie, rozmowy z ludźmi, układanie planów podróży…",
      },
      {
        key: "life_values",
        label: "Co jest najważniejsze w nowym życiu?",
        type: "multi",
        options: [
          "Sens i pomaganie",
          "Wolność i elastyczność",
          "Spokój i mniej stresu",
          "Wyższe zarobki",
          "Kontakt z ludźmi",
          "Rozwój i nauka",
          "Bycie szefem samego siebie",
          "Czas dla rodziny",
        ],
      },
    ],
  },
  {
    title: "Do jakiej branży Cię ciągnie?",
    subtitle: "Zaznacz branże, które Cię ciekawią. Możesz też zostawić to nam.",
    showIf: isIndustry,
    groups: [
      {
        key: "target_industries",
        type: "multi",
        options: [
          "IT i nowe technologie",
          "Finanse i księgowość",
          "Kadry i HR",
          "Logistyka i magazyn",
          "Produkcja",
          "Handel i e-commerce",
          "Marketing i media",
          "Zdrowie i opieka",
          "Edukacja",
          "Budownictwo i energetyka",
          "Administracja publiczna",
          "Turystyka i gastronomia",
          "Nie wiem — zaproponujcie",
        ],
      },
      { key: "leave_reason", label: "Dlaczego chcesz odejść z obecnej branży?", type: "text", placeholder: "np. brak perspektyw, automatyzacja, wypalenie" },
    ],
  },
  {
    title: "Jakie masz wykształcenie?",
    subtitle: "Wybierz najwyższy ukończony poziom.",
    groups: [
      {
        key: "education",
        type: "single",
        required: true,
        options: ["Podstawowe", "Zasadnicze zawodowe", "Średnie", "Średnie techniczne", "Licencjat / inżynier", "Magister", "Doktorat"],
      },
      { key: "education_field", label: "Kierunek, specjalizacja, szkoła", type: "text", placeholder: "np. technik ekonomista, pedagogika" },
    ],
  },
  {
    title: "Co Cię interesuje?",
    subtitle: "Zaznacz wszystko, co sprawia Ci przyjemność.",
    groups: [
      {
        key: "interests",
        type: "multi",
        required: true,
        options: [
          "Technologia i komputery",
          "Praca z ludźmi",
          "Liczby i analizy",
          "Sztuka i design",
          "Natura i zwierzęta",
          "Zdrowie i opieka",
          "Sport",
          "Handel i sprzedaż",
          "Budowanie i naprawianie",
          "Motoryzacja",
          "Języki obce",
          "Uczenie innych",
          "Prawo i przepisy",
          "Media i pisanie",
          "Logistyka i organizacja",
          "Gotowanie",
        ],
      },
      { key: "interests_other", label: "Coś jeszcze? Hobby, pasje", type: "text", placeholder: "np. fotografia, ogrodnictwo" },
    ],
  },
  {
    title: "Czego NIE lubisz w pracy?",
    subtitle: "To równie ważne — tych rzeczy będziemy unikać.",
    groups: [
      {
        key: "dislikes",
        type: "multi",
        options: [
          "Monotonia",
          "Praca przy biurku cały dzień",
          "Kontakt z klientem",
          "Praca fizyczna",
          "Nadgodziny",
          "Praca zmianowa / nocna",
          "Sprzedaż i targety",
          "Częste wyjazdy",
          "Presja czasu",
          "Hałas",
          "Wystąpienia publiczne",
          "Praca w samotności",
        ],
      },
      { key: "dislikes_other", label: "Inne", type: "text", placeholder: "np. nie lubię pracy w weekendy" },
    ],
  },
  {
    title: "Jakie znasz języki?",
    subtitle: "Zaznacz języki obce, którymi się posługujesz.",
    groups: [
      {
        key: "languages",
        type: "multi",
        options: ["Angielski", "Niemiecki", "Ukraiński", "Rosyjski", "Hiszpański", "Francuski", "Włoski", "Niderlandzki", "Czeski", "Norweski"],
      },
      { key: "languages_level", label: "Poziom i inne języki", type: "text", placeholder: "np. angielski B2, niemiecki A2" },
    ],
  },
  {
    title: "Dyplomy, kursy, uprawnienia",
    subtitle: "Wszystko, co już masz, przybliża Cię do celu.",
    groups: [
      {
        key: "certificates",
        type: "multi",
        options: [
          "Prawo jazdy kat. B",
          "Prawo jazdy kat. C / C+E",
          "Uprawnienia UDT (wózki)",
          "Uprawnienia SEP",
          "Excel",
          "Pakiet Office",
          "SAP / systemy ERP",
          "Programy księgowe",
          "Programy kadrowo-płacowe",
          "Canva / Adobe",
          "Programowanie",
          "Kurs pierwszej pomocy",
          "Certyfikat językowy",
          "Kurs BHP",
        ],
      },
      {
        key: "certificates_other",
        label: "Inne dyplomy, kursy i szkolenia",
        type: "text",
        multiline: true,
        placeholder: "np. kurs florystyczny, szkolenie z obsługi klienta, certyfikat ISTQB",
      },
    ],
  },
  {
    title: "Twoje osiągnięcia",
    subtitle: "Z czego jesteś dumny/a? W pracy, nauce lub życiu.",
    groups: [
      {
        key: "achievements",
        type: "text",
        multiline: true,
        placeholder: "np. wdrożyłam nowy system zamówień, zorganizowałem festyn dla 300 osób, wygrałam konkurs…",
      },
    ],
  },
  {
    title: "Jaki masz charakter?",
    subtitle: "Przesuń kropkę bliżej opisu, który bardziej do Ciebie pasuje.",
    groups: [
      {
        key: "personality",
        type: "traits",
        traits: [
          { key: "social", left: "Introwertyk", right: "Ekstrawertyk" },
          { key: "thinking", left: "Analityczny", right: "Kreatywny" },
          { key: "team", left: "Samodzielny", right: "Zespołowy" },
          { key: "stability", left: "Stabilność", right: "Zmiany i wyzwania" },
          { key: "pace", left: "Spokojne tempo", right: "Szybkie tempo" },
          { key: "leading", left: "Wykonawca", right: "Lider" },
        ],
      },
    ],
  },
  {
    title: "Ostatnie szczegóły",
    subtitle: "Pomogą nam dobrać realne oferty i kursy w Twojej okolicy.",
    groups: [
      { key: "work_mode", label: "Jak chcesz pracować?", type: "single", options: ["Zdalnie", "Hybrydowo", "Stacjonarnie", "Bez znaczenia"] },
      {
        key: "learn_time",
        label: "Ile czasu możesz poświęcić na naukę?",
        type: "single",
        options: ["Do 3 miesięcy", "3–12 miesięcy", "1–3 lata (np. studia)", "Bez ograniczeń"],
      },
      { key: "city", label: "Miejscowość", type: "text", placeholder: "np. Poznań" },
    ],
  },
];

// English translations for every literal string above. Used for ALL non-Polish interface
// languages (en/de/nl) — matching the established pattern elsewhere in this app of using
// English as the shared placeholder for DE/NL until dedicated translations are commissioned.
// Falls back to the original Polish text for anything missing, so it can never crash/blank out.
const EN_QUIZ_TEXT: Record<string, string> = {
  // Step 1 — reset mode
  "Jakiej zmiany szukasz?": "What kind of change are you looking for?",
  "Wybierz, jak dużej zmiany szukasz — dopasujemy do tego pytania i propozycje.": "Pick how big a change you're after — we'll tailor the questions and suggestions to it.",
  "Szukam swojej drogi": "I'm looking for my path",
  "Chcę znaleźć pracę, która pasuje do tego, co już umiem i lubię.": "I want to find a job that fits what I already know and enjoy.",
  "Zmieniam branżę": "I'm changing industry",
  "Wykorzystam swoje umiejętności, ale w zupełnie innej branży.": "I'll reuse my skills, but in a completely different industry.",
  "Nowy Rozdział — zmieniam życie": "New Chapter — changing my life",
  "Zaczynam od nowa: inne obowiązki, inny rytm dnia, coś, co naprawdę mnie kręci.": "Starting fresh: different responsibilities, a different daily rhythm, something that truly excites me.",
  // Step 2 — current situation
  "Co robisz obecnie?": "What are you doing right now?",
  "Zacznijmy od Twojej sytuacji — nie ma złych odpowiedzi.": "Let's start with your current situation — there are no wrong answers.",
  "Pracuję i chcę zmienić zawód": "I'm working and want to change profession",
  "Straciłem/am pracę przez AI lub automatyzację": "I lost my job to AI or automation",
  "Szukam pracy": "I'm looking for a job",
  "Uczę się / studiuję": "I'm studying",
  "Dopiero wybieram drogę": "I'm still choosing my path",
  "Prowadzę firmę": "I run a business",
  "Wracam na rynek pracy": "I'm returning to the job market",
  "Obecne lub ostatnie stanowisko i branża": "Current or most recent position and industry",
  "np. kasjerka w markecie, 5 lat": "e.g. supermarket cashier, 5 years",
  // Step 3 — life-reset idea
  "Masz już coś na myśli?": "Do you already have something in mind?",
  "Każdy nowy rozdział zaczyna się od marzenia — nawet jeśli jest jeszcze mgliste.": "Every new chapter starts with a dream — even a vague one.",
  "Tak, wiem, czego chcę": "Yes, I know what I want",
  "Mam kilka luźnych pomysłów": "I have a few loose ideas",
  "Nie, zaskoczcie mnie!": "No, surprise me!",
  "Opisz swój pomysł lub marzenie": "Describe your idea or dream",
  "np. chciałabym pracować ze zwierzętami, otworzyć małą kawiarnię, uczyć jogi…": "e.g. I'd love to work with animals, open a small café, teach yoga…",
  // Step 4 — new directions
  "Jakie kierunki Cię kuszą?": "Which directions tempt you?",
  "Zaznacz wszystko, co brzmi jak nowe, lepsze życie.": "Pick everything that sounds like a new, better life.",
  "Praca z ludźmi i pomaganie": "Working with people & helping",
  "Praca twórcza": "Creative work",
  "Praca na świeżym powietrzu": "Outdoor work",
  "Rękodzieło i rzemiosło": "Crafts & handiwork",
  "Technologia i internet": "Technology & the internet",
  "Własny biznes": "Own business",
  "Praca zdalna z dowolnego miejsca": "Remote work from anywhere",
  "Podróże i praca za granicą": "Travel & working abroad",
  "Zdrowie, sport i wellbeing": "Health, sport & wellbeing",
  "Zwierzęta i natura": "Animals & nature",
  "Edukacja i szkolenia": "Education & training",
  "Kulinaria": "Cooking & culinary",
  // Step 5 — loves / life values
  "Co kochasz robić?": "What do you love doing?",
  "Twoje pasje to najlepsza wskazówka, dokąd iść.": "Your passions are the best clue to where to go.",
  "Przy czym tracisz poczucie czasu?": "What makes you lose track of time?",
  "np. gotowanie dla znajomych, majsterkowanie, rozmowy z ludźmi, układanie planów podróży…": "e.g. cooking for friends, DIY projects, talking to people, planning trips…",
  "Co jest najważniejsze w nowym życiu?": "What matters most in your new life?",
  "Sens i pomaganie": "Meaning & helping others",
  "Wolność i elastyczność": "Freedom & flexibility",
  "Spokój i mniej stresu": "Calm & less stress",
  "Wyższe zarobki": "Higher pay",
  "Kontakt z ludźmi": "Contact with people",
  "Rozwój i nauka": "Growth & learning",
  "Bycie szefem samego siebie": "Being your own boss",
  "Czas dla rodziny": "Time for family",
  // Step 6 — target industries
  "Do jakiej branży Cię ciągnie?": "Which industry draws you in?",
  "Zaznacz branże, które Cię ciekawią. Możesz też zostawić to nam.": "Pick the industries you're curious about. You can also leave it to us.",
  "IT i nowe technologie": "IT & new technologies",
  "Finanse i księgowość": "Finance & accounting",
  "Kadry i HR": "HR & personnel",
  "Logistyka i magazyn": "Logistics & warehousing",
  "Produkcja": "Manufacturing",
  "Handel i e-commerce": "Retail & e-commerce",
  "Marketing i media": "Marketing & media",
  "Zdrowie i opieka": "Health & care",
  "Edukacja": "Education",
  "Budownictwo i energetyka": "Construction & energy",
  "Administracja publiczna": "Public administration",
  "Turystyka i gastronomia": "Tourism & hospitality",
  "Nie wiem — zaproponujcie": "Not sure — surprise me",
  "Dlaczego chcesz odejść z obecnej branży?": "Why do you want to leave your current industry?",
  "np. brak perspektyw, automatyzacja, wypalenie": "e.g. no prospects, automation, burnout",
  // Step 7 — education
  "Jakie masz wykształcenie?": "What's your education level?",
  "Wybierz najwyższy ukończony poziom.": "Choose the highest level you've completed.",
  "Podstawowe": "Primary",
  "Zasadnicze zawodowe": "Basic vocational",
  "Średnie": "Secondary",
  "Średnie techniczne": "Technical secondary",
  "Licencjat / inżynier": "Bachelor's / engineer",
  "Magister": "Master's",
  "Doktorat": "Doctorate",
  "Kierunek, specjalizacja, szkoła": "Field, specialization, school",
  "np. technik ekonomista, pedagogika": "e.g. economics technician, education",
  // Step 8 — interests
  "Co Cię interesuje?": "What interests you?",
  "Zaznacz wszystko, co sprawia Ci przyjemność.": "Pick everything that gives you enjoyment.",
  "Technologia i komputery": "Technology & computers",
  "Praca z ludźmi": "Working with people",
  "Liczby i analizy": "Numbers & analysis",
  "Sztuka i design": "Art & design",
  "Natura i zwierzęta": "Nature & animals",
  "Sport": "Sport",
  "Handel i sprzedaż": "Trade & sales",
  "Budowanie i naprawianie": "Building & fixing things",
  "Motoryzacja": "Automotive",
  "Języki obce": "Foreign languages",
  "Uczenie innych": "Teaching others",
  "Prawo i przepisy": "Law & regulations",
  "Media i pisanie": "Media & writing",
  "Logistyka i organizacja": "Logistics & organization",
  "Gotowanie": "Cooking",
  "Coś jeszcze? Hobby, pasje": "Anything else? Hobbies, passions",
  "np. fotografia, ogrodnictwo": "e.g. photography, gardening",
  // Step 9 — dislikes
  "Czego NIE lubisz w pracy?": "What do you NOT like about work?",
  "To równie ważne — tych rzeczy będziemy unikać.": "This matters just as much — we'll avoid these things.",
  "Monotonia": "Monotony",
  "Praca przy biurku cały dzień": "Desk work all day",
  "Kontakt z klientem": "Customer contact",
  "Praca fizyczna": "Physical labor",
  "Nadgodziny": "Overtime",
  "Praca zmianowa / nocna": "Shift / night work",
  "Sprzedaż i targety": "Sales & targets",
  "Częste wyjazdy": "Frequent travel",
  "Presja czasu": "Time pressure",
  "Hałas": "Noise",
  "Wystąpienia publiczne": "Public speaking",
  "Praca w samotności": "Working alone",
  "Inne": "Other",
  "np. nie lubię pracy w weekendy": "e.g. I don't like working weekends",
  // Step 10 — languages
  "Jakie znasz języki?": "What languages do you know?",
  "Zaznacz języki obce, którymi się posługujesz.": "Pick the foreign languages you speak.",
  "Angielski": "English",
  "Niemiecki": "German",
  "Ukraiński": "Ukrainian",
  "Rosyjski": "Russian",
  "Hiszpański": "Spanish",
  "Francuski": "French",
  "Włoski": "Italian",
  "Niderlandzki": "Dutch",
  "Czeski": "Czech",
  "Norweski": "Norwegian",
  "Poziom i inne języki": "Level & other languages",
  "np. angielski B2, niemiecki A2": "e.g. English B2, German A2",
  // Step 11 — certificates
  "Dyplomy, kursy, uprawnienia": "Diplomas, courses, qualifications",
  "Wszystko, co już masz, przybliża Cię do celu.": "Everything you already have brings you closer to your goal.",
  "Prawo jazdy kat. B": "Driving license cat. B",
  "Prawo jazdy kat. C / C+E": "Driving license cat. C / C+E",
  "Uprawnienia UDT (wózki)": "Forklift license (UDT)",
  "Uprawnienia SEP": "Electrical qualifications (SEP)",
  "Excel": "Excel",
  "Pakiet Office": "Office suite",
  "SAP / systemy ERP": "SAP / ERP systems",
  "Programy księgowe": "Accounting software",
  "Programy kadrowo-płacowe": "Payroll/HR software",
  "Canva / Adobe": "Canva / Adobe",
  "Programowanie": "Programming",
  "Kurs pierwszej pomocy": "First-aid course",
  "Certyfikat językowy": "Language certificate",
  "Kurs BHP": "Health & safety course",
  "Inne dyplomy, kursy i szkolenia": "Other diplomas, courses and training",
  "np. kurs florystyczny, szkolenie z obsługi klienta, certyfikat ISTQB": "e.g. floristry course, customer-service training, ISTQB certificate",
  // Step 12 — achievements
  "Twoje osiągnięcia": "Your achievements",
  "Z czego jesteś dumny/a? W pracy, nauce lub życiu.": "What are you proud of? At work, in school, or in life.",
  "np. wdrożyłam nowy system zamówień, zorganizowałem festyn dla 300 osób, wygrałam konkurs…": "e.g. rolled out a new ordering system, organized a 300-person event, won a competition…",
  // Step 13 — personality
  "Jaki masz charakter?": "What's your personality like?",
  "Przesuń kropkę bliżej opisu, który bardziej do Ciebie pasuje.": "Slide the dot closer to the description that suits you more.",
  "Introwertyk": "Introvert",
  "Ekstrawertyk": "Extrovert",
  "Analityczny": "Analytical",
  "Kreatywny": "Creative",
  "Samodzielny": "Independent",
  "Zespołowy": "Team player",
  "Stabilność": "Stability",
  "Zmiany i wyzwania": "Change & challenges",
  "Spokojne tempo": "Calm pace",
  "Szybkie tempo": "Fast pace",
  "Wykonawca": "Executor",
  "Lider": "Leader",
  // Step 14 — final details
  "Ostatnie szczegóły": "Last details",
  "Pomogą nam dobrać realne oferty i kursy w Twojej okolicy.": "They'll help us pick real offers and courses near you.",
  "Jak chcesz pracować?": "How do you want to work?",
  "Zdalnie": "Remotely",
  "Hybrydowo": "Hybrid",
  "Stacjonarnie": "On-site",
  "Bez znaczenia": "No preference",
  "Ile czasu możesz poświęcić na naukę?": "How much time can you dedicate to learning?",
  "Do 3 miesięcy": "Up to 3 months",
  "3–12 miesięcy": "3–12 months",
  "1–3 lata (np. studia)": "1–3 years (e.g. a degree)",
  "Bez ograniczeń": "No limit",
  "Miejscowość": "City",
  "np. Poznań": "e.g. Warsaw",
};

function tr(text: string, lang: Lang): string {
  if (lang === "pl") return text;
  return EN_QUIZ_TEXT[text] ?? text;
}

function localizeGroup(g: Group, lang: Lang): Group {
  return {
    ...g,
    label: g.label ? tr(g.label, lang) : g.label,
    options: g.options?.map((o) => tr(o, lang)),
    placeholder: g.placeholder ? tr(g.placeholder, lang) : g.placeholder,
    cards: g.cards?.map((c) => ({ ...c, label: tr(c.label, lang), desc: tr(c.desc, lang) })),
    traits: g.traits?.map((tt) => ({ ...tt, left: tr(tt.left, lang), right: tr(tt.right, lang) })),
  };
}

// Returns the quiz question set translated into the given interface language — occupation
// names aren't involved here (this is onboarding Q&A, not AI-generated job content), so there's
// no "keep it local" exception to worry about: every string in the quiz follows ui_language.
export function getQuizSteps(lang: Lang): QuizStep[] {
  if (lang === "pl") return QUIZ_STEPS;
  return QUIZ_STEPS.map((s) => ({ ...s, title: tr(s.title, lang), subtitle: tr(s.subtitle, lang), groups: s.groups.map((g) => localizeGroup(g, lang)) }));
}

export function getResetModes(lang: Lang): Record<string, { label: string; short: string }> {
  if (lang === "pl") return RESET_MODES;
  return Object.fromEntries(Object.entries(RESET_MODES).map(([k, v]) => [k, { label: tr(v.label, lang), short: tr(v.label, lang).toUpperCase() }]));
}

