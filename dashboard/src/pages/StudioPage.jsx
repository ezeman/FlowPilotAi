import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import Card from "../components/Card";
import Spinner from "../components/Spinner";
import StatusPill from "../components/StatusPill";
import { useAuth } from "../context/AuthContext";
import { useLang } from "../context/LangContext";
import { apiRequest } from "../services/api";

const defaultIdea = {
  page_id: "",
  title: "",
  topic: "",
  content_pillar: "Indoor Air",
  target_audience: "เจ้าของบ้านและคนทำงานในอาคาร",
  tone: "professional and friendly",
  post_length: "medium",
  notes: ""
};

const initialBrief = {
  topic: "",
  content_pillar: "Indoor Air",
  target_audience: "คนเมืองและครอบครัว",
  tone: "professional and friendly",
  post_length: "medium",
  reference_notes: "",
  calendar_id: "",
  page_id: ""
};

function formatDate(iso) {
  if (!iso) return "-";
  return new Date(iso).toLocaleString("th-TH", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit"
  });
}

export default function StudioPage() {
  const { hasSubscription } = useAuth();
  const { t } = useLang();
  const subscriptionMessage = "Your account does not have an active subscription. Please submit a payment request from Billing.";
  const [searchParams] = useSearchParams();
  const [activeAgent, setActiveAgent] = useState("strategist");
  const [ideaForm, setIdeaForm] = useState(defaultIdea);
  const [briefForm, setBriefForm] = useState(initialBrief);
  const [pages, setPages] = useState([]);
  const [calendarItems, setCalendarItems] = useState([]);
  const [posts, setPosts] = useState([]);
  const [preview, setPreview] = useState(null);
  const [selectedPageId, setSelectedPageId] = useState("");
  const [discoverySources, setDiscoverySources] = useState([]);
  const [loading, setLoading] = useState(true);
  const [savingIdea, setSavingIdea] = useState(false);
  const [discoveringIdeas, setDiscoveringIdeas] = useState(false);
  const [autoIdeaCount, setAutoIdeaCount] = useState(5);
  const [generating, setGenerating] = useState(false);
  const [savingDraft, setSavingDraft] = useState(false);
  const [reviewingId, setReviewingId] = useState(null);
  const [publishingId, setPublishingId] = useState(null);
  const [imageWorkingId, setImageWorkingId] = useState(null);
  const [multiVariantEnabled, setMultiVariantEnabled] = useState(false);
  const [variantCount, setVariantCount] = useState(3);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const AGENTS = [
    { key: "strategist", name: "Strategist", role: t("studio.agentStrategistRole"), emoji: "01", className: "agent-indigo" },
    { key: "researcher", name: "Researcher", role: t("studio.agentResearcherRole"), emoji: "02", className: "agent-cyan" },
    { key: "writer", name: "Writer", role: t("studio.agentWriterRole"), emoji: "03", className: "agent-emerald" },
    { key: "visualist", name: "Visual Designer", role: t("studio.agentVisualistRole"), emoji: "04", className: "agent-rose" },
    { key: "reviewer", name: "Reviewer", role: t("studio.agentReviewerRole"), emoji: "05", className: "agent-amber" },
    { key: "publisher", name: "Publisher", role: t("studio.agentPublisherRole"), emoji: "06", className: "agent-slate" }
  ];

  const LENGTHS = [
    { value: "short", label: t("common.short") },
    { value: "medium", label: t("common.medium") },
    { value: "long", label: t("common.long") }
  ];

  function pagePreferences(pageId) {
    const page = pages.find((item) => String(item.id) === String(pageId));
    return {
      tone: page?.default_tone || initialBrief.tone,
      content_pillars: Array.isArray(page?.content_pillars) && page.content_pillars.length > 0
        ? page.content_pillars
        : [initialBrief.content_pillar],
    };
  }

  function applyPagePreferencesToIdea(pageId) {
    const preferences = pagePreferences(pageId);
    setIdeaForm((current) => ({
      ...current,
      page_id: pageId,
      tone: preferences.tone,
      content_pillar: preferences.content_pillars[0] || current.content_pillar,
    }));
  }

  function applyPagePreferencesToBrief(pageId) {
    const preferences = pagePreferences(pageId);
    setSelectedPageId(pageId);
    setBriefForm((current) => ({
      ...current,
      page_id: pageId,
      tone: preferences.tone,
      content_pillar: preferences.content_pillars[0] || current.content_pillar,
    }));
  }

  function hydrateBrief(preselectedId, calendarData) {
    if (!preselectedId) return;
    const selected = calendarData.find((item) => String(item.id) === String(preselectedId));
    if (!selected) return;
    setBriefForm({
      topic: selected.topic || selected.title || "",
      content_pillar: selected.content_pillar || initialBrief.content_pillar,
      target_audience: selected.target_audience || initialBrief.target_audience,
      tone: selected.tone || initialBrief.tone,
      post_length: selected.post_length || initialBrief.post_length,
      reference_notes: selected.notes || "",
      calendar_id: String(selected.id),
      page_id: selected.page_id ? String(selected.page_id) : ""
    });
    if (selected.page_id) setSelectedPageId(String(selected.page_id));
  }

  async function loadData({ keepMessage = true } = {}) {
    setLoading(true);
    if (!keepMessage) setMessage("");
    try {
      const [calendarData, pageData, postsData, sourceData] = await Promise.all([
        apiRequest("/content-calendar"),
        apiRequest("/pages"),
        apiRequest("/posts"),
        apiRequest("/content-calendar/sources")
      ]);
      setCalendarItems(calendarData);
      setPages(pageData);
      setPosts(postsData);
      setDiscoverySources(sourceData);
      hydrateBrief(searchParams.get("calendar_id"), calendarData);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadData();
  }, []);

  useEffect(() => {
    if (!message) return undefined;
    const timer = setTimeout(() => setMessage(""), 4500);
    return () => clearTimeout(timer);
  }, [message]);

  const reviewPosts = useMemo(
    () => posts.filter((post) => ["draft", "ready_for_review", "approved"].includes(post.status)),
    [posts]
  );
  const approvedPosts = useMemo(() => posts.filter((post) => post.status === "approved"), [posts]);
  const visualPosts = useMemo(
    () => posts.filter((post) => ["draft", "ready_for_review", "approved"].includes(post.status)),
    [posts]
  );

  async function saveIdea(event) {
    event.preventDefault();
    if (!hasSubscription) {
      setError(subscriptionMessage);
      return;
    }
    setSavingIdea(true);
    setError("");
    try {
      const created = await apiRequest("/content-calendar", {
        method: "POST",
        body: JSON.stringify({
          ...ideaForm,
          page_id: ideaForm.page_id ? Number(ideaForm.page_id) : null
        })
      });
      setIdeaForm(defaultIdea);
      setMessage(t("studio.savedIdea"));
      setActiveAgent("researcher");
      await loadData();
      if (created?.id) hydrateBrief(created.id, [...calendarItems, created]);
    } catch (err) {
      setError(err.message);
    } finally {
      setSavingIdea(false);
    }
  }

  async function autoDiscoverIdeas() {
    if (!hasSubscription) {
      setError(subscriptionMessage);
      return;
    }
    setDiscoveringIdeas(true);
    setError("");
    try {
      const response = await apiRequest("/content-calendar/auto-ideas", {
        method: "POST",
        body: JSON.stringify({ count: Number(autoIdeaCount), save_to_calendar: true })
      });
      setDiscoverySources(response.sources_checked || []);
      setMessage(t("studio.ideasAutoCreated").replace("{count}", response.items?.length || 0));
      await loadData();
    } catch (err) {
      setError(err.message);
    } finally {
      setDiscoveringIdeas(false);
    }
  }

  function handleCalendarPick(value) {
    const selected = calendarItems.find((item) => String(item.id) === value);
    setBriefForm((current) => ({
      ...current,
      calendar_id: value,
      topic: selected?.topic || selected?.title || current.topic,
      content_pillar: selected?.content_pillar || current.content_pillar,
      target_audience: selected?.target_audience || current.target_audience,
      tone: selected?.tone || current.tone,
      post_length: selected?.post_length || current.post_length,
      reference_notes: selected?.notes || current.reference_notes,
      page_id: selected?.page_id ? String(selected.page_id) : current.page_id
    }));
    if (selected?.page_id) setSelectedPageId(String(selected.page_id));
  }

  async function generateDraft(event) {
    event.preventDefault();
    if (!hasSubscription) {
      setError(subscriptionMessage);
      return;
    }
    setGenerating(true);
    setError("");
    setPreview(null);
    try {
      const generated = await apiRequest("/posts/ai/generate", {
        method: "POST",
        body: JSON.stringify({
          topic: briefForm.topic,
          content_pillar: briefForm.content_pillar,
          target_audience: briefForm.target_audience,
          tone: briefForm.tone,
          post_length: briefForm.post_length,
          reference_notes: briefForm.reference_notes,
          page_id: selectedPageId || briefForm.page_id ? Number(selectedPageId || briefForm.page_id) : null,
          post_id: null
        })
      });
      setPreview(generated);
      setActiveAgent("writer");
      setMessage(t("studio.draftSaved"));
    } catch (err) {
      setError(err.message);
    } finally {
      setGenerating(false);
    }
  }

  async function saveDraft() {
    if (!preview) return;
    if (!hasSubscription) {
      setError(subscriptionMessage);
      return;
    }
    setSavingDraft(true);
    setError("");
    try {
      await apiRequest("/posts", {
        method: "POST",
        body: JSON.stringify({
          calendar_id: briefForm.calendar_id ? Number(briefForm.calendar_id) : null,
          page_id: selectedPageId ? Number(selectedPageId) : null,
          title: preview.title,
          caption: preview.caption,
          hashtags: preview.hashtags,
          image_prompt: preview.image_prompt,
          content_pillar: briefForm.content_pillar,
          target_audience: briefForm.target_audience,
          tone: briefForm.tone,
          post_length: briefForm.post_length,
          status: "draft",
          reference_notes: briefForm.reference_notes
        })
      });
      setPreview(null);
      setMessage(t("studio.draftSaved"));
      setActiveAgent("visualist");
      await loadData();
    } catch (err) {
      setError(err.message);
    } finally {
      setSavingDraft(false);
    }
  }

  async function createVisualBrief(postId) {
    if (!hasSubscription) {
      setError(subscriptionMessage);
      return;
    }
    setImageWorkingId(postId);
    setError("");
    try {
      await apiRequest(`/posts/${postId}/visual-brief`, { method: "POST" });
      setMessage(t("studio.visualBriefCreated"));
      await loadData();
    } catch (err) {
      setError(err.message);
    } finally {
      setImageWorkingId(null);
    }
  }

  async function generateImageAsset(postId) {
    if (!hasSubscription) {
      setError(subscriptionMessage);
      return;
    }
    setImageWorkingId(postId);
    setError("");
    try {
      const requestedVariantCount = multiVariantEnabled ? Number(variantCount) : 1;
      await apiRequest(`/posts/${postId}/generate-image`, {
        method: "POST",
        body: JSON.stringify({ variant_count: requestedVariantCount })
      });
      setMessage(
        requestedVariantCount === 1
          ? t("studio.imageCreated")
          : t("studio.imagesCreated").replace("{count}", requestedVariantCount)
      );
      await loadData();
    } catch (err) {
      setError(err.message);
    } finally {
      setImageWorkingId(null);
    }
  }

  async function decide(postId, approved) {
    if (!hasSubscription) {
      setError(subscriptionMessage);
      return;
    }
    setReviewingId(postId);
    setError("");
    try {
      await apiRequest(`/posts/${postId}/approve`, {
        method: "POST",
        body: JSON.stringify({
          approved,
          notes: approved ? null : "ต้องการการปรับแก้เพิ่มเติม"
        })
      });
      setMessage(approved ? t("studio.postApproved") : t("studio.postSentBack"));
      await loadData();
      if (approved) setActiveAgent("publisher");
    } catch (err) {
      setError(err.message);
    } finally {
      setReviewingId(null);
    }
  }

  async function publishNow(postId) {
    if (!hasSubscription) {
      setError(subscriptionMessage);
      return;
    }
    setPublishingId(postId);
    setError("");
    try {
      await apiRequest(`/posts/${postId}/publish`, { method: "POST" });
      setMessage(t("studio.publishRequested"));
      await loadData();
    } catch (err) {
      setError(err.message);
    } finally {
      setPublishingId(null);
    }
  }

  const summary = [
    { label: "Ideas", value: calendarItems.length },
    { label: "Visual Queue", value: visualPosts.length },
    { label: "Review Queue", value: reviewPosts.length },
    { label: "Approved", value: approvedPosts.length }
  ];

  const currentAgent = AGENTS.find((agent) => agent.key === activeAgent) || AGENTS[0];

  return (
    <div className="page-stack">
      <section className="hero-banner">
        <div>
          <div className="eyebrow">{t("studio.eyebrow")}</div>
          <h1>{t("studio.title")}</h1>
          <p>{t("studio.subtitle")}</p>
        </div>
        <div className="hero-actions">
          <button className="primary-button" type="button" onClick={() => setActiveAgent("strategist")}>
            {t("studio.startNew")}
          </button>
          <button className="secondary-button" type="button" onClick={() => loadData({ keepMessage: false })}>
            {t("studio.refreshQueue")}
          </button>
        </div>
      </section>

      <div className="studio-summary">
        {summary.map((item) => (
          <div key={item.label} className="summary-tile">
            <p>{item.label}</p>
            <strong>{item.value}</strong>
          </div>
        ))}
      </div>

      <div className="agents-pipeline">
        {AGENTS.map((agent) => (
          <button
            key={agent.key}
            type="button"
            className={`agent-card ${agent.className} ${activeAgent === agent.key ? "active" : ""}`}
            onClick={() => setActiveAgent(agent.key)}
          >
            <span className="agent-emoji">{agent.emoji}</span>
            <div className="agent-name">{agent.name}</div>
            <p className="agent-role">{agent.role}</p>
            <span className="agent-badge">{t("studio.agentBadge")}</span>
          </button>
        ))}
      </div>

      {error && <div className="inline-error">{error}</div>}
      {!hasSubscription && (
        <div className="subscription-warning">
          <div>
            <strong>{subscriptionMessage}</strong>
          </div>
          <Link className="primary-button" to="/billing">Billing</Link>
        </div>
      )}
      {message && <div className="inline-success">{message}</div>}

      {loading ? (
        <div className="loading-center">
          <Spinner />
        </div>
      ) : (
        <section className="workspace-panel">
          <div className="workspace-header">
            <div>
              <div className="workspace-title">{currentAgent.name}</div>
              <div className="workspace-subtitle">{currentAgent.role}</div>
            </div>
            <div className="workspace-header-emoji">{currentAgent.emoji}</div>
          </div>

          <div className="workspace-body">
            {activeAgent === "strategist" && (
              <div className="workspace-split">
                <Card title={t("studio.newIdeaBriefTitle")} subtitle={t("studio.newIdeaBriefSubtitle")} variant="glass">
                  <form className="stack-form" onSubmit={saveIdea}>
                    <label>
                      Page
                      <select value={ideaForm.page_id} onChange={(event) => applyPagePreferencesToIdea(event.target.value)} required={pages.length > 0}>
                        <option value="">Select page</option>
                        {pages.map((page) => (
                          <option key={page.id} value={page.id}>
                            {page.name}
                          </option>
                        ))}
                      </select>
                    </label>
                    <div className="form-grid">
                      <label>
                        {t("studio.ideaName")}
                        <input value={ideaForm.title} onChange={(event) => setIdeaForm({ ...ideaForm, title: event.target.value })} required />
                      </label>
                      <label>
                        Topic
                        <input value={ideaForm.topic} onChange={(event) => setIdeaForm({ ...ideaForm, topic: event.target.value })} required />
                      </label>
                    </div>
                    <div className="form-grid">
                      <label>
                        Content Pillar
                        {pagePreferences(ideaForm.page_id).content_pillars.length > 1 ? (
                          <select value={ideaForm.content_pillar} onChange={(event) => setIdeaForm({ ...ideaForm, content_pillar: event.target.value })}>
                            {pagePreferences(ideaForm.page_id).content_pillars.map((pillar) => (
                              <option key={pillar} value={pillar}>{pillar}</option>
                            ))}
                          </select>
                        ) : (
                          <input value={ideaForm.content_pillar} onChange={(event) => setIdeaForm({ ...ideaForm, content_pillar: event.target.value })} />
                        )}
                      </label>
                      <label>
                        Target Audience
                        <input value={ideaForm.target_audience} onChange={(event) => setIdeaForm({ ...ideaForm, target_audience: event.target.value })} />
                      </label>
                    </div>
                    <div className="form-grid">
                      <label>
                        Tone
                        <input value={ideaForm.tone} onChange={(event) => setIdeaForm({ ...ideaForm, tone: event.target.value })} />
                      </label>
                      <label>
                        {t("common.postLength")}
                        <select value={ideaForm.post_length} onChange={(event) => setIdeaForm({ ...ideaForm, post_length: event.target.value })}>
                          {LENGTHS.map((item) => (
                            <option key={item.value} value={item.value}>
                              {item.label}
                            </option>
                          ))}
                        </select>
                      </label>
                    </div>
                    <label>
                      Notes
                      <textarea rows="5" value={ideaForm.notes} onChange={(event) => setIdeaForm({ ...ideaForm, notes: event.target.value })} />
                    </label>
                    <div className="button-row" style={{ alignItems: "center" }}>
                      <button className="primary-button" type="submit" disabled={savingIdea || !hasSubscription} title={!hasSubscription ? subscriptionMessage : undefined}>
                        {savingIdea ? t("studio.savingIdea") : t("studio.saveToCalendar")}
                      </button>
                      <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
                        <select
                          value={autoIdeaCount}
                          onChange={(event) => setAutoIdeaCount(Number(event.target.value))}
                          disabled={discoveringIdeas || !hasSubscription}
                          style={{ width: "4.5rem" }}
                        >
                          {[1, 2, 3, 4, 5].map((n) => (
                            <option key={n} value={n}>{n} idea{n > 1 ? "s" : ""}</option>
                          ))}
                        </select>
                        <button className="secondary-button" type="button" onClick={autoDiscoverIdeas} disabled={discoveringIdeas || !hasSubscription} title={!hasSubscription ? subscriptionMessage : undefined}>
                          {discoveringIdeas ? t("studio.discoveringIdeas") : `${t("studio.autoDiscover")} (${autoIdeaCount})`}
                        </button>
                      </div>
                    </div>
                  </form>
                </Card>

                <div className="page-stack">
                  <Card title={t("studio.latestIdeas")} subtitle={t("studio.latestIdeasSubtitle")} variant="glass">
                    <div className="stack-blocks">
                      {calendarItems.slice(0, 5).map((item) => (
                        <div key={item.id} className="surface-panel" style={{ padding: "0.95rem" }}>
                          <div className="surface-row" style={{ paddingTop: 0 }}>
                            <strong>{item.title}</strong>
                            <StatusPill status={item.status} />
                          </div>
                          <p>{item.topic || t("common.noTopic")}</p>
                          <div className="button-row" style={{ marginTop: "0.8rem" }}>
                            <button
                              className="secondary-button"
                              type="button"
                              onClick={() => {
                                handleCalendarPick(String(item.id));
                                setActiveAgent("researcher");
                              }}
                            >
                              {t("studio.usedAsSourceBrief")}
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  </Card>

                  <Card title={t("studio.trustedSources")} subtitle={t("studio.trustedSourcesSubtitle")} variant="glass">
                    <div className="stack-blocks">
                      {discoverySources.map((source) => (
                        <div key={source.id} className="surface-panel" style={{ padding: "0.95rem" }}>
                          <strong>{source.name}</strong>
                          <p className="muted-label" style={{ marginTop: "0.25rem" }}>{source.content_pillar}</p>
                          <a href={source.url} target="_blank" rel="noreferrer" style={{ color: "var(--primary)", fontSize: "0.84rem" }}>
                            {source.url}
                          </a>
                        </div>
                      ))}
                    </div>
                  </Card>
                </div>
              </div>
            )}

            {activeAgent === "researcher" && (
              <div className="workspace-split">
                <Card title={t("studio.sourceBriefTitle")} subtitle={t("studio.sourceBriefSubtitle")} variant="glass">
                  <form className="stack-form" onSubmit={generateDraft}>
                    <label>
                      {t("studio.selectFromCalendar")}
                      <select value={briefForm.calendar_id} onChange={(event) => handleCalendarPick(event.target.value)}>
                        <option value="">{t("studio.specifyOwnTopic")}</option>
                        {calendarItems.map((item) => (
                          <option key={item.id} value={item.id}>
                            {item.title}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label>
                      Page
                      <select value={selectedPageId || briefForm.page_id} onChange={(event) => applyPagePreferencesToBrief(event.target.value)}>
                        <option value="">{t("studio.selectPageLater")}</option>
                        {pages.map((page) => (
                          <option key={page.id} value={page.id}>
                            {page.name}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label>
                      Topic
                      <input value={briefForm.topic} onChange={(event) => setBriefForm({ ...briefForm, topic: event.target.value })} required />
                    </label>
                    <div className="form-grid">
                      <label>
                        Content Pillar
                        {pagePreferences(selectedPageId || briefForm.page_id).content_pillars.length > 1 ? (
                          <select value={briefForm.content_pillar} onChange={(event) => setBriefForm({ ...briefForm, content_pillar: event.target.value })}>
                            {pagePreferences(selectedPageId || briefForm.page_id).content_pillars.map((pillar) => (
                              <option key={pillar} value={pillar}>{pillar}</option>
                            ))}
                          </select>
                        ) : (
                          <input value={briefForm.content_pillar} onChange={(event) => setBriefForm({ ...briefForm, content_pillar: event.target.value })} />
                        )}
                      </label>
                      <label>
                        Target Audience
                        <input value={briefForm.target_audience} onChange={(event) => setBriefForm({ ...briefForm, target_audience: event.target.value })} />
                      </label>
                    </div>
                    <div className="form-grid">
                      <label>
                        Tone
                        <input value={briefForm.tone} onChange={(event) => setBriefForm({ ...briefForm, tone: event.target.value })} />
                      </label>
                      <label>
                        {t("common.postLength")}
                        <select value={briefForm.post_length} onChange={(event) => setBriefForm({ ...briefForm, post_length: event.target.value })}>
                          {LENGTHS.map((item) => (
                            <option key={item.value} value={item.value}>
                              {item.label}
                            </option>
                          ))}
                        </select>
                      </label>
                    </div>
                    <label>
                      Reference Notes
                      <textarea rows="5" value={briefForm.reference_notes} onChange={(event) => setBriefForm({ ...briefForm, reference_notes: event.target.value })} />
                    </label>
                    <div className="button-row">
                      <button className="primary-button" type="submit" disabled={generating || !hasSubscription} title={!hasSubscription ? subscriptionMessage : undefined}>
                        {generating ? t("studio.generating") : t("studio.sendToWriter")}
                      </button>
                    </div>
                  </form>
                </Card>

                <Card title={t("studio.contextWatchlist")} subtitle={t("studio.contextWatchlistSubtitle")} variant="glass">
                  <div className="stack-blocks">
                    <div className="panel-note">{t("studio.researcherNote")}</div>
                    <div className="surface-row">
                      <span>{t("studio.ideasInSystem")}</span>
                      <strong>{calendarItems.length}</strong>
                    </div>
                    <div className="surface-row">
                      <span>{t("studio.connectedPages")}</span>
                      <strong>{pages.length}</strong>
                    </div>
                    <div className="surface-row">
                      <span>{t("studio.reviewQueue")}</span>
                      <strong>{reviewPosts.length}</strong>
                    </div>
                  </div>
                </Card>
              </div>
            )}

            {activeAgent === "writer" && (
              <div className="workspace-split">
                <Card title={t("studio.draftPreviewTitle")} subtitle={t("studio.draftPreviewSubtitle")} variant="glass">
                  {generating ? (
                    <div className="loading-center">
                      <Spinner />
                    </div>
                  ) : preview ? (
                    <div className="stack-blocks">
                      <div>
                        <h3>{preview.title}</h3>
                        <p className="muted-label" style={{ marginTop: "0.35rem" }}>
                          {t("studio.qualityScore")}: {preview.quality_score ?? "-"}
                        </p>
                      </div>
                      <p className="preview-copy">{preview.caption}</p>
                      <p className="muted-label">Hashtags: {preview.hashtags?.join(" ") || "-"}</p>
                      <p className="muted-label">Image Prompt: {preview.image_prompt || "-"}</p>
                      <label>
                        {t("studio.assignPage")}
                        <select value={selectedPageId} onChange={(event) => setSelectedPageId(event.target.value)}>
                          <option value="">{t("studio.selectPageLater")}</option>
                          {pages.map((page) => (
                            <option key={page.id} value={page.id}>
                              {page.name}
                            </option>
                          ))}
                        </select>
                      </label>
                      <div className="button-row">
                        <button className="primary-button" type="button" onClick={saveDraft} disabled={savingDraft || !hasSubscription} title={!hasSubscription ? subscriptionMessage : undefined}>
                          {savingDraft ? t("studio.savingDraft") : t("studio.saveAsDraft")}
                        </button>
                        <button className="ghost-button" type="button" onClick={() => setActiveAgent("researcher")}>
                          {t("studio.backToBrief")}
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="empty-state">
                      <p>{t("studio.noPreview")}</p>
                      <p>{t("studio.noPreviewHint")}</p>
                    </div>
                  )}
                </Card>

                <Card title={t("studio.referenceSuggestions")} subtitle={t("studio.referenceSuggestionsSubtitle")} variant="glass">
                  {preview?.reference_suggestions?.length ? (
                    <ul className="simple-list">
                      {preview.reference_suggestions.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  ) : (
                    <div className="panel-note">{t("studio.referenceSuggestionsNote")}</div>
                  )}
                </Card>
              </div>
            )}

            {activeAgent === "visualist" && (
              <Card title={t("studio.visualDesignDesk")} subtitle={t("studio.visualDesignSubtitle")} variant="glass">
                <div className="panel-note" style={{ marginBottom: "1rem" }}>
                  {t("studio.visualNote")}
                </div>
                <div className="stack-blocks" style={{ marginBottom: "1rem" }}>
                  <label style={{ display: "flex", alignItems: "center", gap: "0.65rem", fontWeight: 700 }}>
                    <input
                      type="checkbox"
                      checked={multiVariantEnabled}
                      onChange={(event) => setMultiVariantEnabled(event.target.checked)}
                    />
                    {t("studio.enableMultiVariants")}
                  </label>
                  {multiVariantEnabled ? (
                    <label style={{ maxWidth: "220px" }}>
                      {t("studio.variantCount")}
                      <select value={variantCount} onChange={(event) => setVariantCount(Number(event.target.value))}>
                        <option value={2}>2 variants</option>
                        <option value={3}>3 variants</option>
                        <option value={4}>4 variants</option>
                      </select>
                    </label>
                  ) : null}
                </div>
                {visualPosts.length === 0 ? (
                  <div className="empty-state centered">
                    <p>{t("studio.noPostsForVisual")}</p>
                  </div>
                ) : (
                  <div className="posts-list">
                    {visualPosts.map((post) => (
                      <div key={post.id} className="post-item" style={{ alignItems: "flex-start" }}>
                        <div className="post-item-info">
                          <div className="post-item-title">{post.title || t("common.noName")}</div>
                          <div className="post-item-meta">
                            {post.content_pillar || t("common.uncategorized")} · {t("common.asset")} {post.assets?.length || 0} · {t("common.updated")} {formatDate(post.updated_at)}
                          </div>
                          <p className="muted-label" style={{ marginTop: "0.65rem" }}>
                            Prompt: {post.image_prompt || t("studio.noVisualBrief")}
                          </p>
                          {post.assets?.[0]?.asset_url ? (
                            <div style={{ marginTop: "0.8rem" }}>
                              <img
                                src={post.assets[0].asset_url}
                                alt={post.assets[0].alt_text || post.title}
                                style={{ width: "128px", borderRadius: "16px", border: "1px solid var(--line)" }}
                              />
                            </div>
                          ) : null}
                        </div>
                        <StatusPill status={post.status} />
                        <div className="button-row">
                          <button
                            className="secondary-button"
                            type="button"
                            onClick={() => createVisualBrief(post.id)}
                            disabled={imageWorkingId === post.id || !hasSubscription}
                            title={!hasSubscription ? subscriptionMessage : undefined}
                          >
                            {imageWorkingId === post.id ? <Spinner size="sm" /> : t("studio.createVisualBrief")}
                          </button>
                          <button
                            className="primary-button"
                            type="button"
                            onClick={() => generateImageAsset(post.id)}
                            disabled={imageWorkingId === post.id || !hasSubscription}
                            title={!hasSubscription ? subscriptionMessage : undefined}
                          >
                            {imageWorkingId === post.id
                              ? <Spinner size="sm" />
                              : multiVariantEnabled
                                ? `Generate ${variantCount} Variants`
                                : t("studio.generateImage")}
                          </button>
                          <Link className="ghost-button" to={`/posts/${post.id}/edit`}>
                            {t("common.openEditor")}
                          </Link>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </Card>
            )}

            {activeAgent === "reviewer" && (
              <Card title={t("studio.reviewQueueTitle")} subtitle={t("studio.reviewQueueSubtitle")} variant="glass">
                {reviewPosts.length === 0 ? (
                  <div className="empty-state centered">
                    <p>{t("studio.noPostsToReview")}</p>
                  </div>
                ) : (
                  <div className="review-list">
                    {reviewPosts.map((post) => (
                      <article key={post.id} className="review-item">
                        <div className="review-headline">
                          <div>
                            <h3>{post.title || t("common.noName")}</h3>
                            <p className="muted-label" style={{ marginTop: "0.25rem" }}>
                              {t("common.updated")} {formatDate(post.updated_at)} · {t("common.asset")} {post.assets?.length || 0}
                            </p>
                          </div>
                          <StatusPill status={post.status} />
                        </div>
                        <p className="preview-copy">{post.caption || t("reviewQueue.noCaption")}</p>
                        {post.hashtags?.length > 0 && <p className="muted-label">{post.hashtags.join(" ")}</p>}
                        <div className="button-row" style={{ marginTop: "0.8rem" }}>
                          {post.status !== "approved" && (
                            <button
                              className="primary-button"
                              type="button"
                              onClick={() => decide(post.id, true)}
                              disabled={reviewingId === post.id || !hasSubscription}
                              title={!hasSubscription ? subscriptionMessage : undefined}
                            >
                              {reviewingId === post.id ? <Spinner size="sm" /> : t("studio.postApproved")}
                            </button>
                          )}
                          <button
                            className="secondary-button"
                            type="button"
                            onClick={() => decide(post.id, false)}
                            disabled={reviewingId === post.id || !hasSubscription}
                            title={!hasSubscription ? subscriptionMessage : undefined}
                          >
                            {t("studio.sendBackForEdit")}
                          </button>
                          <Link className="ghost-button" to={`/posts/${post.id}/edit`}>
                            {t("common.openEditor")}
                          </Link>
                        </div>
                      </article>
                    ))}
                  </div>
                )}
              </Card>
            )}

            {activeAgent === "publisher" && (
              <Card title={t("studio.publishDeskTitle")} subtitle={t("studio.publishDeskSubtitle")} variant="glass">
                {approvedPosts.length === 0 ? (
                  <div className="empty-state centered">
                    <p>{t("studio.noApprovedPosts")}</p>
                  </div>
                ) : (
                  <div className="posts-list">
                    {approvedPosts.map((post) => (
                      <div key={post.id} className="post-item">
                        <div className="post-item-info">
                          <div className="post-item-title">{post.title || t("common.noName")}</div>
                          <div className="post-item-meta">
                            Page: {post.page_id || t("common.notSet")} · {t("common.asset")} {post.assets?.length || 0} · {t("common.updated")} {formatDate(post.updated_at)}
                          </div>
                        </div>
                        <StatusPill status={post.status} />
                        <div className="button-row">
                          <Link className="secondary-button" to={`/posts/${post.id}/schedule`}>
                            Schedule
                          </Link>
                          <button
                            className="primary-button"
                            type="button"
                            onClick={() => publishNow(post.id)}
                            disabled={publishingId === post.id || !hasSubscription}
                            title={!hasSubscription ? subscriptionMessage : undefined}
                          >
                            {publishingId === post.id ? <Spinner size="sm" /> : t("studio.publishNow")}
                          </button>
                          <Link className="ghost-button" to={`/posts/${post.id}/edit`}>
                            Edit
                          </Link>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </Card>
            )}
          </div>
        </section>
      )}
    </div>
  );
}
