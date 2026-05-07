import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import Card from "../components/Card";
import { useLang } from "../context/LangContext";
import { apiRequest } from "../services/api";

const defaultIdea = {
  title: "",
  topic: "",
  content_pillar: "Indoor Air",
  target_audience: "เจ้าของบ้านและคนทำงานในอาคาร",
  tone: "professional and friendly",
  post_length: "medium",
  notes: ""
};

const PILLARS = ["Indoor Air", "Outdoor Air", "Health", "CO2", "VOC", "Mold", "Ventilation", "Climate", "Lifestyle"];

export default function CreateIdeaPage() {
  const { t } = useLang();
  const [form, setForm] = useState(defaultIdea);
  const [savedId, setSavedId] = useState(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  const LENGTHS = [
    { value: "short", label: t("common.short") },
    { value: "medium", label: t("common.medium") },
    { value: "long", label: t("common.long") }
  ];

  useEffect(() => {
    if (message) {
      const timer = setTimeout(() => setMessage(""), 6000);
      return () => clearTimeout(timer);
    }
  }, [message]);

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    setMessage("");
    setSaving(true);

    try {
      const created = await apiRequest("/content-calendar", {
        method: "POST",
        body: JSON.stringify(form)
      });
      setSavedId(created?.id || null);
      setMessage(t("createIdea.savedMsg"));
      setForm(defaultIdea);
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
          <p className="eyebrow">{t("createIdea.eyebrow")}</p>
          <h1>{t("createIdea.title")}</h1>
          <p>{t("createIdea.subtitle")}</p>
        </div>
      </section>

      <Card>
        <form className="stack-form" onSubmit={handleSubmit}>
          <div className="form-grid">
            <label>
              {t("createIdea.ideaName")}
              <input
                value={form.title}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
                placeholder={t("createIdea.ideaNamePlaceholder")}
                required
              />
            </label>
            <label>
              {t("createIdea.mainTopic")}
              <input
                value={form.topic}
                onChange={(e) => setForm({ ...form, topic: e.target.value })}
                placeholder={t("createIdea.mainTopicPlaceholder")}
                required
              />
            </label>
          </div>

          <div className="form-grid">
            <label>
              {t("createIdea.contentPillar")}
              <select
                value={form.content_pillar}
                onChange={(e) => setForm({ ...form, content_pillar: e.target.value })}
              >
                {PILLARS.map((p) => (
                  <option key={p} value={p}>{p}</option>
                ))}
              </select>
            </label>
            <label>
              {t("createIdea.targetAudience")}
              <input
                value={form.target_audience}
                onChange={(e) => setForm({ ...form, target_audience: e.target.value })}
              />
            </label>
          </div>

          <div className="form-grid">
            <label>
              {t("createIdea.tone")}
              <input
                value={form.tone}
                onChange={(e) => setForm({ ...form, tone: e.target.value })}
                placeholder={t("createIdea.tonePlaceholder")}
              />
            </label>
            <label>
              {t("createIdea.postLength")}
              <select
                value={form.post_length}
                onChange={(e) => setForm({ ...form, post_length: e.target.value })}
              >
                {LENGTHS.map((l) => (
                  <option key={l.value} value={l.value}>{l.label}</option>
                ))}
              </select>
            </label>
          </div>

          <label>
            {t("createIdea.additionalNotes")}
            <textarea
              value={form.notes}
              onChange={(e) => setForm({ ...form, notes: e.target.value })}
              rows="4"
              placeholder={t("createIdea.notesPlaceholder")}
            />
          </label>

          {error && <div className="inline-error">{error}</div>}
          {message && (
            <div className="inline-success">
              {message}
              {savedId && (
                <span>
                  {" "}—{" "}
                  <Link to={`/ai-generate?calendar_id=${savedId}`} style={{ color: "inherit", textDecoration: "underline" }}>
                    {t("createIdea.createPostLink")}
                  </Link>
                </span>
              )}
            </div>
          )}

          <div className="button-row">
            <button className="primary-button" type="submit" disabled={saving}>
              {saving ? t("createIdea.saving") : t("createIdea.save")}
            </button>
            <Link className="secondary-button" to="/calendar">
              {t("createIdea.viewCalendar")}
            </Link>
          </div>
        </form>
      </Card>
    </div>
  );
}
