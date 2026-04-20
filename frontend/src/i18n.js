import i18n from 'i18next';
import LanguageDetector from 'i18next-browser-languagedetector';
import { initReactI18next } from 'react-i18next';

import en from './locales/en';
import zhCN from './locales/zh-CN';

export const ENGLISH_LOCALE = 'en';
export const CHINESE_LOCALE = 'zh-CN';
export const DEFAULT_LOCALE = ENGLISH_LOCALE;
export const LOCALE_STORAGE_KEY = 'memory-palace.locale';
export const SUPPORTED_LOCALES = [ENGLISH_LOCALE, CHINESE_LOCALE];

const normalizeDetectedLocale = (lng) => {
  const normalized = String(lng || '').trim();
  if (!normalized) return DEFAULT_LOCALE;

  const lowerCased = normalized.toLowerCase();
  if (
    lowerCased === CHINESE_LOCALE.toLowerCase()
    || lowerCased === 'zh'
    || lowerCased.startsWith('zh-')
  ) {
    return CHINESE_LOCALE;
  }
  if (lowerCased === ENGLISH_LOCALE || lowerCased.startsWith('en-')) {
    return ENGLISH_LOCALE;
  }
  return normalized;
};

const resolveFallbackLocales = (lng) => {
  const normalized = normalizeDetectedLocale(lng);
  if (normalized === CHINESE_LOCALE) {
    return [CHINESE_LOCALE];
  }
  return [DEFAULT_LOCALE];
};

const readStoredLocale = (storage) => {
  if (!storage) return null;
  try {
    const stored = storage.getItem(LOCALE_STORAGE_KEY);
    return stored ? normalizeDetectedLocale(stored) : null;
  } catch (_error) {
    return null;
  }
};

/**
 * @param {{
 *   storage?: Storage | null,
 *   navigatorLike?: Pick<Navigator, 'language' | 'languages'> | null,
 * }} [options]
 */
export const resolveBootstrapLocale = (options = {}) => {
  const { storage, navigatorLike } = options;
  const resolvedStorage = storage ?? (typeof window !== 'undefined' ? window.localStorage : null);
  const storedLocale = readStoredLocale(resolvedStorage);
  if (storedLocale && SUPPORTED_LOCALES.includes(storedLocale)) {
    return storedLocale;
  }

  const fallbackNavigator = navigatorLike ?? (typeof window !== 'undefined' ? window.navigator : null);
  const navigatorCandidates = [];
  if (Array.isArray(fallbackNavigator?.languages)) {
    navigatorCandidates.push(...fallbackNavigator.languages);
  }
  if (fallbackNavigator?.language) {
    navigatorCandidates.push(fallbackNavigator.language);
  }

  for (const candidate of navigatorCandidates) {
    const normalized = normalizeDetectedLocale(candidate);
    if (SUPPORTED_LOCALES.includes(normalized)) {
      return normalized;
    }
  }

  return DEFAULT_LOCALE;
};

export const getDocumentTitleForLocale = (lng) => (
  normalizeDetectedLocale(lng) === CHINESE_LOCALE
    ? zhCN.app.documentTitle
    : en.app.documentTitle
);

export const primeDocumentLanguageFromBootstrap = (options = {}) => {
  const locale = resolveBootstrapLocale(options);
  if (typeof document !== 'undefined') {
    document.documentElement.lang = locale;
    document.documentElement.dir = 'ltr';
    document.title = getDocumentTitleForLocale(locale);
  }
  return locale;
};

const syncDocumentLanguage = (lng) => {
  if (typeof document === 'undefined') return;
  const language = lng || i18n.resolvedLanguage || DEFAULT_LOCALE;
  document.documentElement.lang = language;
  document.documentElement.dir = i18n.dir(language);
  document.title = getDocumentTitleForLocale(language);
};

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      [CHINESE_LOCALE]: { translation: zhCN },
      [ENGLISH_LOCALE]: { translation: en },
    },
    fallbackLng: resolveFallbackLocales,
    supportedLngs: SUPPORTED_LOCALES,
    detection: {
      order: ['localStorage', 'navigator'],
      caches: ['localStorage'],
      lookupLocalStorage: LOCALE_STORAGE_KEY,
      convertDetectedLanguage: normalizeDetectedLocale,
    },
    interpolation: {
      escapeValue: false,
    },
    returnNull: false,
    react: {
      useSuspense: false,
    },
  })
  .then(() => {
    syncDocumentLanguage(i18n.resolvedLanguage);
  });

i18n.on('languageChanged', syncDocumentLanguage);

export default i18n;
