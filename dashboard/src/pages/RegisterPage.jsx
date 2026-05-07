import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { useAuth } from "../context/AuthContext";
import { useLang } from "../context/LangContext";
import LanguageSwitcher from "../components/LanguageSwitcher";
import { apiRequest } from "../services/api";

export default function RegisterPage() {
  const navigate = useNavigate();
  const { loginWithToken } = useAuth();
  const { t } = useLang();
  const [form, setForm] = useState({
    account_name: "",
    full_name: "",
    email: "",
    password: "",
    confirm_password: "",
  });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [verificationToken, setVerificationToken] = useState(null);

  function field(key) {
    return (event) => setForm((prev) => ({ ...prev, [key]: event.target.value }));
  }

  async function handleSubmit(event) {
    event.preventDefault();
    if (form.password !== form.confirm_password) {
      setError(t("register.passwordMismatch"));
      return;
    }
    setLoading(true);
    setError("");
    try {
      const data = await apiRequest("/auth/register", {
        method: "POST",
        body: JSON.stringify(form),
      });
      setVerificationToken(data.verification_token);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleVerify() {
    setLoading(true);
    setError("");
    try {
      const data = await apiRequest(`/auth/verify-email?token=${encodeURIComponent(verificationToken)}`);
      loginWithToken(data.access_token);
      navigate("/");
    } catch (err) {
      setError(err.message);
      setLoading(false);
    }
  }

  if (verificationToken) {
    return (
      <div className="login-shell">
        <div className="login-panel">
          <div className="eyebrow" style={{ color: "var(--primary)" }}>FlowPilot AI</div>
          <h1>{t("register.verifyTitle")}</h1>
          <p>{t("register.verifySubtitle")}</p>
          <div className="surface-panel" style={{ marginTop: "1.5rem", padding: "1rem", wordBreak: "break-all", fontSize: "0.8rem", fontFamily: "monospace" }}>
            <p style={{ marginBottom: "0.4rem", fontWeight: 700, fontFamily: "sans-serif" }}>{t("register.verificationToken")}</p>
            {verificationToken}
          </div>
          <p style={{ marginTop: "0.75rem", fontSize: "0.82rem", color: "var(--text-muted)" }}>
            {t("register.verifyNote")}
          </p>
          {error && <div className="inline-error" style={{ marginTop: "0.75rem" }}>{error}</div>}
          <button className="primary-button" type="button" onClick={handleVerify} disabled={loading} style={{ marginTop: "1rem", width: "100%" }}>
            {loading ? t("register.verifying") : t("register.verifySubmit")}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="login-shell">
      <div className="login-panel">
        <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: "0.75rem" }}>
          <LanguageSwitcher />
        </div>
        <div className="eyebrow" style={{ color: "var(--primary)" }}>FlowPilot AI</div>
        <h1>{t("register.title")}</h1>
        <p>{t("register.subtitle")}</p>
        <form className="stack-form" onSubmit={handleSubmit} style={{ marginTop: "1.5rem" }}>
          <label>
            {t("register.accountName")}
            <input value={form.account_name} onChange={field("account_name")} required minLength={2} placeholder="Acme Co." />
          </label>
          <label>
            {t("register.fullName")}
            <input value={form.full_name} onChange={field("full_name")} required minLength={2} placeholder="สมชาย ใจดี" />
          </label>
          <label>
            {t("register.email")}
            <input type="email" value={form.email} onChange={field("email")} required placeholder="you@company.com" />
          </label>
          <label>
            {t("register.password")}
            <input type="password" value={form.password} onChange={field("password")} required minLength={8} placeholder={t("register.passwordPlaceholder")} />
          </label>
          <label>
            {t("register.confirmPassword")}
            <input type="password" value={form.confirm_password} onChange={field("confirm_password")} required minLength={8} />
          </label>
          {error && <div className="inline-error">{error}</div>}
          <button className="primary-button" type="submit" disabled={loading}>
            {loading ? t("register.submitting") : t("register.submit")}
          </button>
        </form>
        <p style={{ marginTop: "1.2rem", fontSize: "0.85rem", textAlign: "center", color: "var(--text-muted)" }}>
          {t("register.hasAccount")}{" "}
          <Link to="/login" style={{ color: "var(--primary)" }}>
            {t("register.loginLink")}
          </Link>
        </p>
      </div>
    </div>
  );
}
