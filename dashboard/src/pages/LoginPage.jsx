import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { useAuth } from "../context/AuthContext";
import { useLang } from "../context/LangContext";
import LanguageSwitcher from "../components/LanguageSwitcher";

export default function LoginPage() {
  const navigate = useNavigate();
  const { login } = useAuth();
  const { t } = useLang();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      await login(email, password);
      navigate("/");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="login-shell">
      <div className="login-panel">
        <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: "0.75rem" }}>
          <LanguageSwitcher />
        </div>
        <div className="eyebrow" style={{ color: "var(--primary)" }}>ezeCraft AI</div>
        <p style={{ margin: "0.1rem 0 0.6rem", fontSize: "0.8rem", color: "var(--text-muted)", fontStyle: "italic" }}>Craft is Easy.</p>
        <h1>{t("login.title")}</h1>
        <p>{t("login.subtitle")}</p>
        <form className="stack-form" onSubmit={handleSubmit} style={{ marginTop: "1.5rem" }}>
          <label>
            {t("login.email")}
            <input value={email} onChange={(event) => setEmail(event.target.value)} type="email" required />
          </label>
          <label>
            {t("login.password")}
            <input value={password} onChange={(event) => setPassword(event.target.value)} type="password" required />
          </label>
          {error && <div className="inline-error">{error}</div>}
          <button className="primary-button" type="submit" disabled={loading}>
            {loading ? t("login.submitting") : t("login.submit")}
          </button>
        </form>
        <p style={{ marginTop: "1.2rem", fontSize: "0.85rem", textAlign: "center", color: "var(--text-muted)" }}>
          {t("login.noAccount")}{" "}
          <Link to="/register" style={{ color: "var(--primary)" }}>
            {t("login.register")}
          </Link>
        </p>
      </div>
    </div>
  );
}
