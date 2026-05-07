import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

import Card from "../components/Card";
import Spinner from "../components/Spinner";
import { useLang } from "../context/LangContext";
import { apiRequest } from "../services/api";

const initialForm = {
  topic: "",
  content_pillar: "Indoor Air",
  target_audience: "คนเมืองและครอบครัว",
  tone: "professional and friendly",
  post_length: "medium",
  reference_notes: "",
  calendar_id: ""
};

export default function GenerateContentPage() {
  const [searchParams] = useSearchParams();
  const { t } = useLang();
  const [form, setForm] = useState(initialForm);
  const [calendarItems, setCalendarItems] = useState([]);
  const [pages, setPages] = useState([]);
  const [selectedPageId, setSelectedPageId] = useState("");
  const [preview, setPreview] = useState(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const LENGTHS = [
    { value: "short", label: t("common.short") },
    { value: "medium", label: t("common.medium") },
    { value: "long", label: t("common.long") }
  ];

  useEffect(() => {
    if (message) {
      const timer = setTimeout(() => setMessage(""), 5000);
      return () => clearTimeout(timer);
    }
  }, [message]);

  useEffect(() => {
    const preselectedId = searchParams.get("calendar_id");

    Promise.all([apiRequest("/content-calendar"), apiRequest("/pages")])
      .then(([calendarData, pageData]) => {
        setCalendarItems(calendarData);
        setPages(pageData);

        if (preselectedId) {
          const selected = calendarData.find((item) => String(item.id) === preselectedId);
          if (selected) {
            setForm({
              ...initialForm,
              calendar_id: preselectedId,
              topic: selected.topic || selected.title || "",
              content_pillar: selected.content_pillar || initialForm.content_pillar,
              target_audience: selected.target_audience || initialForm.target_audience,
              tone: selected.tone || initialForm.tone,
              post_length: selected.post_length || initialForm.post_length,
              reference_notes: selected.notes || ""
            });
          }
        }
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  function handleCalendarChange(event) {
    const value = event.target.value;
    const selected = calendarItems.find((item) => String(item.id) === value);
    setForm({
      ...form,
      calendar_id: value,
      topic: selected?.topic || selected?.title || form.topic,
      content_pillar: selected?.content_pillar || form.content_pillar,
      target_audience: selected?.target_audience || form.target_audience,
      tone: selected?.tone || form.tone,
      post_length: selected?.post_length || form.post_length,
      reference_notes: selected?.notes || form.reference_notes
    });
  }

  async function handleGenerate(event) {
    event.preventDefault();
    setError("");
    setMessage("");
    setGenerating(true);
    setPreview(null);
    try {
      const generated = await apiRequest("/posts/ai/generate", {
        method: "POST",
        body: JSON.stringify({ ...form, calendar_id: undefined, post_id: null })
      });
      setPreview(generated);
    } catch (err) {
      setError(err.message);
    } finally {
      setGenerating(false);
    }
  }

  async function saveDraftFromPreview() {
    if (!preview) return;
    setError("");
    setSaving(true);
    try {
      await apiRequest("/posts", {
        method: "POST",
        body: JSON.stringify({
          calendar_id: form.calendar_id ? Number(form.calendar_id) : null,
          page_id: selectedPageId ? Number(selectedPageId) : null,
          title: preview.title,
          caption: preview.caption,
          hashtags: preview.hashtags,
          image_prompt: preview.image_prompt,
          content_pillar: form.content_pillar,
          target_audience: form.target_audience,
          tone: form.tone,
          post_length: form.post_length,
          status: "draft",
          reference_notes: form.reference_notes
        })
      });
      setMessage(t("generate.draftSavedMsg"));
      setPreview(null);
      setForm(initialForm);
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
          <p className="eyebrow">{t("generate.eyebrow")}</p>
          <h1>{t("generate.title")}</h1>
          <p>{t("generate.subtitle")}</p>
        </div>
      </section>

      {loading ? (
        <div className="loading-center">
          <Spinner />
        </div>
      ) : (
        <div className="page-stack two-column-layout">
          <Card title={t("generate.formTitle")} subtitle={t("generate.formSubtitle")}>
            <form className="stack-form" onSubmit={handleGenerate}>
              <label>
                {t("generate.selectFromCalendar")}
                <select value={form.calendar_id} onChange={handleCalendarChange}>
                  <option value="">{t("generate.specifyTopic")}</option>
                  {calendarItems.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.title}
                    </option>
                  ))}
                </select>
              </label>

              <label>
                {t("generate.postTopic")}
                <input
                  value={form.topic}
                  onChange={(e) => setForm({ ...form, topic: e.target.value })}
                  placeholder={t("generate.postTopicPlaceholder")}
                  required
                />
              </label>

              <div className="form-grid">
                <label>
                  {t("generate.contentPillar")}
                  <input
                    value={form.content_pillar}
                    onChange={(e) => setForm({ ...form, content_pillar: e.target.value })}
                  />
                </label>
                <label>
                  {t("generate.targetAudience")}
                  <input
                    value={form.target_audience}
                    onChange={(e) => setForm({ ...form, target_audience: e.target.value })}
                  />
                </label>
              </div>

              <div className="form-grid">
                <label>
                  {t("generate.tone")}
                  <input
                    value={form.tone}
                    onChange={(e) => setForm({ ...form, tone: e.target.value })}
                  />
                </label>
                <label>
                  {t("generate.postLength")}
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
                {t("generate.referenceNotes")}
                <textarea
                  value={form.reference_notes}
                  onChange={(e) => setForm({ ...form, reference_notes: e.target.value })}
                  rows="4"
                  placeholder={t("generate.referenceNotesPlaceholder")}
                />
              </label>

              {pages.length > 0 && (
                <label>
                  {t("generate.facebookPage")}
                  <select value={selectedPageId} onChange={(e) => setSelectedPageId(e.target.value)}>
                    <option value="">{t("generate.selectPageLater")}</option>
                    {pages.map((page) => (
                      <option key={page.id} value={page.id}>
                        {page.name}
                      </option>
                    ))}
                  </select>
                </label>
              )}

              {error && <div className="inline-error">{error}</div>}
              {message && <div className="inline-success">{message}</div>}

              <button className="primary-button" type="submit" disabled={generating}>
                {generating ? (
                  <span style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                    <Spinner size="sm" />
                    {t("generate.generating")}
                  </span>
                ) : (
                  t("generate.generateButton")
                )}
              </button>
            </form>
          </Card>

          <Card title={t("generate.previewTitle")} subtitle={t("generate.previewSubtitle")}>
            {generating ? (
              <div className="loading-center">
                <Spinner />
              </div>
            ) : preview ? (
              <div className="stack-blocks">
                <div>
                  <h3>{preview.title}</h3>
                  <p className="muted-label" style={{ marginTop: "0.25rem" }}>
                    {t("generate.qualityScore")} {preview.quality_score}
                  </p>
                </div>
                <p className="preview-copy">{preview.caption}</p>
                <p className="muted-label">{t("generate.hashtags")} {preview.hashtags?.join(" ")}</p>
                <p className="muted-label">{t("generate.imagePrompt")} {preview.image_prompt}</p>
                {preview.reference_suggestions?.length > 0 && (
                  <div>
                    <p className="muted-label" style={{ marginBottom: "0.5rem" }}>{t("generate.referenceSuggestions")}</p>
                    <ul className="simple-list">
                      {preview.reference_suggestions.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  </div>
                )}
                <button className="primary-button" type="button" onClick={saveDraftFromPreview} disabled={saving}>
                  {saving ? t("generate.savingDraft") : t("generate.saveDraft")}
                </button>
              </div>
            ) : (
              <div className="empty-state">
                <p>{t("generate.previewEmpty")}</p>
                <p>{t("generate.previewHint")}</p>
              </div>
            )}
          </Card>
        </div>
      )}
    </div>
  );
}
