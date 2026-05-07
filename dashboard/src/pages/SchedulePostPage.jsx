import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import Card from "../components/Card";
import { useLang } from "../context/LangContext";
import { apiRequest } from "../services/api";

export default function SchedulePostPage() {
  const { postId } = useParams();
  const navigate = useNavigate();
  const { t } = useLang();
  const [scheduledFor, setScheduledFor] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      await apiRequest(`/posts/${postId}/schedule`, {
        method: "POST",
        body: JSON.stringify({ scheduled_for: new Date(scheduledFor).toISOString() })
      });
      navigate(`/posts/${postId}/edit`);
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
          <div className="eyebrow">{t("schedule.eyebrow")}</div>
          <h1>{t("schedule.title")}</h1>
          <p>{t("schedule.subtitle")}</p>
        </div>
      </section>

      <Card title={t("schedule.cardTitle")} subtitle={t("schedule.cardSubtitle")} variant="glass">
        <form className="stack-form" onSubmit={handleSubmit}>
          <label>
            {t("schedule.dateTimeLabel")}
            <input
              type="datetime-local"
              value={scheduledFor}
              onChange={(event) => setScheduledFor(event.target.value)}
              required
            />
          </label>
          {error && <div className="inline-error">{error}</div>}
          <div className="button-row">
            <button className="primary-button" type="submit" disabled={saving}>
              {saving ? t("schedule.saving") : t("schedule.confirm")}
            </button>
            <button className="ghost-button" type="button" onClick={() => navigate(`/posts/${postId}/edit`)}>
              {t("schedule.cancel")}
            </button>
          </div>
        </form>
      </Card>
    </div>
  );
}
