// Shape of every translatable static UI string in the app. Every language file in this
// folder (pl.ts/en.ts/de.ts/nl.ts) must implement this exact shape — TypeScript will flag
// any missing/extra key. AI-GENERATED content (career descriptions, roadmap/plan items) is
// NOT part of this file: the backend already returns that in the right language per career
// (see career_cache_key / "country" fields on server.py) — this file only covers the app's
// own static chrome (buttons, headers, empty/error states).
export type Strings = {
  common: {
    appName: string; // short brand label, e.g. in "{appName} Premium"
    appNameFull: string; // full name shown on the big auth-screen logo
    loading: string;
    retry: string;
    cancel: string;
    pleaseWait: string;
    aiNote: string; // disclaimer shown under any AI-generated advice
  };
  ads: {
    reasonEditQuiz: string; // used when editing survey answers
    reasonRegenerateCareers: string; // "Wygeneruj nowe propozycje"
    reasonGetCareers: string; // finishing the quiz
    reasonBuildPath: string; // choosing a career path
    reasonWeeklyPlan: string;
    reasonDailyPlan: string; // building/saving the daily plan settings
    reasonNextWeek: string;
    reasonRestOfWeek: string;
    reasonNextBlock: string;
    reasonRestoreStreak: string;
    defaultReason: string; // fallback used when no specific reason string is passed
    adLabel: string; // "REKLAMA" pill when there's only one ad
    adLabelCounted: (index: number, total: number) => string; // "REKLAMA 1/2"
    introTitleQuota: string;
    introTitleSecond: string;
    introTitleFirst: string;
    introTitleInterstitial: string;
    introTextQuota: (total: number, reason: string) => string;
    introTextMultiSecond: (reason: string) => string;
    introTextMultiFirst: (total: number, reason: string) => string;
    introTextSingle: (reason: string) => string;
    introTextInterstitial: string;
    playingTitle: string;
    playingNoteSim: string;
    playingLoading: string;
    countdown: (s: number) => string;
    countdownEnding: string;
    thanksTitleMore: string;
    thanksTitleDone: string;
    thanksTextMore: string;
    thanksTextDone: (rewarded: boolean, appName: string) => string;
    watchButton: string;
    goPremiumButton: string;
    nextAdButton: string;
    continueButton: string;
  };
  countrySelect: {
    title: string;
    subtitle: string;
    langSuffix: string; // "Treści AI w języku {lang}" — {lang} substituted
  };
  auth: {
    loginTab: string;
    registerTab: string;
    nameLabel: string;
    namePlaceholder: string;
    emailLabel: string;
    emailLabelLogin: string;
    emailPlaceholderLogin: string;
    passwordLabel: string;
    passwordPlaceholder: string;
    confirmPasswordLabel: string;
    confirmPasswordPlaceholder: string;
    passwordMismatch: string;
    forgotPassword: string;
    loginButton: string;
    registerButton: string;
    invalidEmail: string;
    invalidLoginId: string;
    shortPassword: string;
    heroTagline: string;
    matchSuffix: string; // "dopasowania" after a %
    features: string[];
    welcomeBackTitle: string;
    findCareerTitle: string;
    loginSubtitle: string;
    registerSubtitle: string;
    jobs: { title: string; area: string; icon: string; match: number }[];
    skills: { label: string; icon: string }[];
  };
  forgotPassword: {
    title: string;
    subtitle: string;
    emailLabel: string;
    sendCode: string;
    checkInboxTitle: string;
    checkInboxInfo: (email: string) => string;
    codeLabel: string;
    newPasswordLabel: string;
    newPasswordPlaceholder: string;
    confirmPasswordLabel: string;
    confirmPasswordPlaceholder: string;
    passwordMismatch: string;
    submit: string;
    resend: string;
    invalidEmail: string;
    invalidCode: string;
    shortPassword: string;
  };
  tabs: {
    careers: string;
    road: string;
    profile: string;
  };
  weekdays: {
    short: string[]; // 7 short labels, Monday first
    full: string[]; // 7 full lowercase names, Monday first
    today: string; // "TODAY" badge appended next to today's date
  };
  quiz: {
    stepIndicator: (step: number, total: number) => string; // "Question 2 of 6"
    adNotice: string; // shown above the final "show my careers" button
    nextButton: string;
    finishButton: string;
  };
  aiInfo: {
    title: string; // "Before you start" one-time info modal shown on cold start
    body1: string;
    body2: (premium: boolean) => string;
    premiumNote: (limit: number) => string;
    freeNote: (limit: number) => string;
    dismissButton: string;
  };
  matches: {
    headerFallback: string;
    title: string;
    tabNow: string;
    tabFuture: string;
    customGoal: string;
    analyzing: string;
    genError: string;
    emptyText: string;
    startQuiz: string;
    subtitleNow: string;
    subtitleFuture: string;
    emptyCategory: string;
    matchSuffix: string;
    demandLabel: string;
    aiRiskLabel: string;
  };
  career: {
    badgeNow: string;
    badgeFuture: string;
    matchSuffix: string;
    loadingDetail: string;
    sectionWhatYouDo: string;
    sectionPros: string;
    sectionCons: string;
    sectionRequirements: string;
    sectionHowToStart: string;
    sectionCareerLevels: string;
    sectionJobOffers: string;
    adNotice: string;
    goPremiumInline: string;
    limitReached: string;
    managePaths: string;
    chooseButton: string;
    celebrateTitle: string;
    celebrateText: (title?: string) => string;
  };
  road: {
    headerKicker: string;
    titleFallback: string;
    studyPlan: string;
    emptyTitle: string;
    emptyText: string;
    goToMatches: string;
    buildingTitle: string;
    buildingText: string;
    genError: string;
    hint: string;
    deleteTitle: string;
    deleteText: (title?: string) => string;
    deleteConfirm: string;
    deleteCancel: string;
  };
  plan: {
    screenTitle: string; // header title for the whole /plan screen
    dailyTab: string;
    weeklyTab: string;
    dailyPremiumTitle: string;
    dailyPremiumText: string;
    goPremium: string;
    buildingTitle: string;
    buildingText: string;
    dailyBuildingTitle: string; // pending state while the daily plan is generated
    freeSettingsTitle: string;
    timeModeDaily: string;
    timeModeWeekly: string;
    chipDaily: string; // short chip label, "Daily"
    chipWeekly: string; // short chip label, "Weekly"
    minutesPerDay: string;
    hoursPerWeek: string;
    freeDaysLabel: string;
    createButton: string;
    emptyTitle: string;
    emptyText: string;
    weeklyEmptyTitle: string;
    weeklyEmptyText: string;
    weeklyCreateAdNotice: string;
    weeklyCreateButton: string;
    nextBlockAdNotice: string;
    nextBlockButton: string;
    perWeekSuffix: string;
    tipsTitle: string;
    weekLabel: string;
    nextWeekButton: string;
    nextWeekAdNotice: string;
    restOfWeekButton: string;
    restOfWeekAdNotice: string;
    goalLabel: string;
    genError: string; // daily/weekly plan generation failed
    errorPositiveNumber: string;
    errorKeepOneDay: string;
    editSettingsTitle: string; // heading when re-editing an existing daily plan
    dailyFormSubtitle: string;
    timeQuestionLabel: string;
    freeDaysQuestion: string;
    saveAndRebuildButton: string;
    weekChipLabel: (n: number) => string; // "Week {n}" switcher chip (daily plan)
    weekProgressLabel: (done: number, total: number) => string;
    dayOffLabel: string;
    lockedDayLabel: (count: number) => string;
    noItemsForDay: string;
    weeklyBadge: string; // "every week" badge on recurring items
    unlockWeekButton: string;
    generatingNextWeek: string;
    nextWeekLockedHint: string;
    changeSettingsButton: string;
    stepsLabel: string;
    freeLabel: string;
    materialsLabel: string;
    blockChipLabel: (start: number, end: number) => string; // "Weeks {start}-{end}" (study plan)
    approxHoursPerWeek: (hours: number) => string;
  };
  profile: {
    titleFallback: string;
    premiumHeading: string;
    adminRow: string;
    adminSub: string;
    premiumActiveTitle: string;
    premiumActiveSub: string;
    premiumInactiveTitle: string;
    premiumInactiveSub: string;
    planRow: string;
    planRowSub: string;
    countryHeading: string;
    countrySub: string;
    styleHeading: string;
    answersHeading: string;
    editQuiz: string;
    editQuizSub: string;
    regenerate: string;
    regenerateSub: string;
    regeneratePleaseWait: string;
    adNotice: string;
    logout: string;
    langSuffix: string;
  };
  premium: {
    heroTitle: string;
    heroSub: string;
    activeTitle: string;
    activeUsage: (used: number, limit: number) => string;
    perkNoAdsTitle: string;
    perkNoAdsText: string;
    perkQuotaTitle: string;
    perkQuotaText: string;
    monthlyLabel: string;
    monthlyNote: string;
    yearlyLabel: string;
    yearlyNote: string;
    perMonth: string;
    perYear: string;
    demoNotice: string;
    cancelButton: string;
    subscribeButton: string;
    cancelConfirmTitle: string;
    cancelConfirmText: (limit: number) => string;
    keepPremiumButton: string;
    continueCancelButton: string;
    reasonModalTitle: string;
    reasonModalSubtitle: string;
    reasonTooExpensive: string;
    reasonNoLongerNeeded: string;
    reasonNotSatisfied: string;
    reasonGotJob: string;
    reasonOther: string;
    reasonOtherPlaceholder: string;
    confirmCancelButton: string;
  };
  customPath: {
    title: string;
    subtitle: string;
    titleLabel: string;
    titlePlaceholder: string;
    qualificationsLabel: string;
    qualificationsHint: string;
    qualificationsPlaceholder: string;
    submit: string;
  };
  streak: {
    lostTitle: (n: number) => string;
    lostText: string;
    restoreButton: string;
    restartButton: string;
    activeTitle: (count: number) => string;
    activeText: (best: number) => string;
    closeButton: string;
    lostCardTitle: string;
    lostCardSub: string;
  };
};
