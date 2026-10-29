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
    title: "Jaki reset Cię interesuje?",
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
