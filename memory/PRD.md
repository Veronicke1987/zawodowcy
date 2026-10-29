# Reset – aplikacja do przebranżowienia (PRD)

## Original problem statement
Aplikacja na Sklep Play "Reset" do przebranżowienia / wyboru ścieżki zawodowej. Ankieta (obecna praca, wykształcenie, zainteresowania, czego nie lubi, języki, dyplomy, kursy, osiągnięcia, charakter) → propozycje zawodów w 2 kategoriach (już teraz / wymagają nauki), oparte o wymagania z ofert (Pracuj.pl, OLX, LinkedIn). Szczegóły zawodu: opis, plusy, minusy, jak zacząć. Ścieżka kariery jako droga z dużymi punktami (stanowiska) i małymi (zadania), dźwięk po wyborze ścieżki, podpowiedzi z linkami (YouTube, kursy, studia, urząd pracy).

## User choices
- AI analizuje profil i rynek pracy (bez scrapowania), linki wyszukiwania do portali
- Modele: Claude Sonnet 5.5 (analiza, propozycje, droga) + GPT 6 Luna (opis zawodu, podpowiedzi) – Emergent LLM key
- Logowanie e-mail + hasło (JWT)
- 3 przełączane style: Świeży / Spokojny / Ciemny

## Architecture
- Backend FastAPI + MongoDB (users, profiles, recommendations, career_details, roadmaps); LLM jobs w tle z job_id + polling
- Frontend Expo Router: auth, quiz (9 kroków), (tabs): Zawody / Droga / Profil, career/[id]; road SVG (react-native-svg), dźwięk expo-audio, ikony Ionicons, font Plus Jakarta Sans

## Implemented (2026-06)
- Auth JWT, admin seed, ankieta, propozycje AI, opis zawodu + linki do ofert, wybór ścieżki z dźwiękiem i animacją, droga z punktami i odhaczaniem, arkusz podpowiedzi z linkami, przełącznik motywów. Testy: iteracja 1 i 2 zaliczone.

## Iteration 2 (2026-06)
- Czat „Doradca kariery” (GPT 6 Luna, streaming SSE), 5 darmowych pytań/dzień (licznik w chat_usage, nie resetuje się po czyszczeniu czatu), Premium bez limitu
- Premium w trybie DEMO (19,99 zł/mies., 149,99 zł/rok): do 3 ścieżek naraz (darmowo 1), 8-tygodniowy plan nauki (Claude Sonnet 5.5)
- Wiele ścieżek: /api/paths, przełączanie, usuwanie; ekrany /chat, /premium, /plan. Testy: iteracja 3 zaliczona + poprawki

## Iteration 3 (2026-06)
- Logowanie loginem: admin `ADMIN` / `Test@123` (także admin@reset.app); pole „E-mail lub login”; cały interfejs po polsku

## Iteration 4 (2026-06)
- Tryby resetu w ankiecie: „Szukam swojej drogi”, „Zmieniam branżę” (+pytanie o branże), „Wielki Reset — zmieniam życie” (+3 pytania: pomysł, kierunki, pasje/wartości); AI w trybie Wielki Reset nie proponuje nic z obecnej branży
- Admin właścicielki: weronisia1987s@gmail.com (ADMIN_EMAILS) — staje się adminem przy rejestracji
- Panel administratora /admin: statystyki, nadawanie darmowego Premium po e-mailu (także przed rejestracją), przełącznik Premium per użytkownik, wyszukiwarka

## Iteration 5 (2026-06)
- „Wielki Reset” → „Nowy Rozdział — zmieniam życie”; nowy obrazek logowania (zespół przy pracy), hasło „Zmiana zawodu i nowa ścieżka kariery” + 3 punkty o funkcjach aplikacji

## Backlog
- P0: Prawdziwe płatności (subskrypcja Google Play) zamiast trybu demo
- P1: Udostępnianie postępu / drogi, przypomnienia o nauce, kilka ścieżek równolegle
- P2: Prawdziwe oferty pracy na żywo, plan premium, edycja profilu (imię)
