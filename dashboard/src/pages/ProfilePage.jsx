import { useEffect, useState } from "react";

import Card from "../components/Card";
import { useAuth } from "../context/AuthContext";
import { useLang } from "../context/LangContext";
import { apiRequest } from "../services/api";

const emptyPw = { current_password: "", new_password: "", confirm_password: "" };

export default function ProfilePage() {
  const { user } = useAuth();
  const { t } = useLang();
  const [pwForm, setPwForm] = useState(emptyPw);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!message) return undefined;
    const timer = setTimeout(() => setMessage(""), 4000);
    return () => clearTimeout(timer);
  }, [message]);

  function pwField(key) {
    return (event) => setPwForm((prev) => ({ ...prev, [key]: event.target.value }));
  }

  async function handleChangePassword(event) {
    event.preventDefault();
    if (pwForm.new_password !== pwForm.confirm_password) {
      setError(t("profile.passwordMismatch"));
      return;
    }
    setSaving(true);
    setError("");
    try {
      await apiRequest("/auth/change-password", {
        method: "POST",
        body: JSON.stringify({
          current_password: pwForm.current_password,
          new_password: pwForm.new_password,
        }),
      });
      setMessage(t("profile.successMsg"));
      setPwForm(emptyPw);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="page-stack">
      <section className="hero-banner">
        <div>
          <div className="eyebrow">{t("profile.eyebrow")}</div>
          <h1>{user?.full_name || "Profile"}</h1>
          <p>
            {user?.email} · {user?.role}
          </p>
        </div>
      </section>

      {error && <div className="inline-error">{error}</div>}
      {message && <div className="inline-success">{message}</div>}

      <div className="two-column-layout">
        <Card title={t("profile.accountInfo")} subtitle={t("profile.accountInfoSubtitle")} variant="glass">
          <div className="stack-blocks">
            <div className="surface-row">
              <span>{t("profile.name")}</span>
              <strong>{user?.full_name}</strong>
            </div>
            <div className="surface-row">
              <span>{t("profile.email")}</span>
              <strong>{user?.email}</strong>
            </div>
            <div className="surface-row">
              <span>{t("profile.role")}</span>
              <span className="status-pill">{user?.role}</span>
            </div>
            <div className="surface-row">
              <span>{t("profile.workspace")}</span>
              <strong>{user?.account?.name || t("profile.platform")}</strong>
            </div>
          </div>
        </Card>

        <Card title={t("profile.changePassword")} subtitle={t("profile.changePasswordSubtitle")} variant="glass">
          <form className="stack-form" onSubmit={handleChangePassword}>
            <label>
              {t("profile.currentPassword")}
              <input type="password" value={pwForm.current_password} onChange={pwField("current_password")} required />
            </label>
            <label>
              {t("profile.newPassword")}
              <input type="password" value={pwForm.new_password} onChange={pwField("new_password")} required minLength={8} placeholder={t("profile.passwordPlaceholder")} />
            </label>
            <label>
              {t("profile.confirmNewPassword")}
              <input type="password" value={pwForm.confirm_password} onChange={pwField("confirm_password")} required minLength={8} />
            </label>
            <button className="primary-button" type="submit" disabled={saving}>
              {saving ? t("profile.saving") : t("profile.submit")}
            </button>
          </form>
        </Card>
      </div>
    </div>
  );
}
