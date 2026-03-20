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

const syncDocumentLanguage = (lng) => {
  if (typeof document === 'undefined') return;
  const language = lng || i18n.resolvedLanguage || DEFAULT_LOCALE;
  document.documentElement.lang = language;
  document.documentElement.dir = i18n.dir(language);
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
    react: {
      useSuspense: false,
    },
  })
  .then(() => {
    syncDocumentLanguage(i18n.resolvedLanguage);
  });

i18n.on('languageChanged', syncDocumentLanguage);

export default i18n;
