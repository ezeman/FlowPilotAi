import { createContext, useContext, useState } from "react";
import th from "../i18n/th.json";
import en from "../i18n/en.json";

const translations = { th, en };
const LangContext = createContext(null);

export function LangProvider({ children }) {
  const [lang, setLangState] = useState(() => localStorage.getItem("fp_lang") || "th");

  function setLang(l) {
    localStorage.setItem("fp_lang", l);
    setLangState(l);
  }

  function t(key) {
    const parts = key.split(".");
    let val = translations[lang];
    for (const p of parts) {
      val = val?.[p];
      if (val === undefined) break;
    }
    return val ?? key;
  }

  return <LangContext.Provider value={{ lang, setLang, t }}>{children}</LangContext.Provider>;
}

export function useLang() {
  return useContext(LangContext);
}
