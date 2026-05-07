import { useLang } from "../context/LangContext";

export default function LanguageSwitcher() {
  const { lang, setLang } = useLang();
  return (
    <div className="lang-switcher">
      <button type="button" className={lang === "th" ? "lang-btn active" : "lang-btn"} onClick={() => setLang("th")}>TH</button>
      <button type="button" className={lang === "en" ? "lang-btn active" : "lang-btn"} onClick={() => setLang("en")}>EN</button>
    </div>
  );
}
