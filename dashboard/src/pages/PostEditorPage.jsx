import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import Card from "../components/Card";
import Spinner from "../components/Spinner";
import StatusPill from "../components/StatusPill";
import { useAuth } from "../context/AuthContext";
import { useLang } from "../context/LangContext";
import { apiRequest } from "../services/api";

function formatDate(iso) {
  if (!iso) return "-";
  return new Date(iso).toLocaleString("th-TH", {
    year: "numeric",
    month: "long",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit"
  });
}

export default function PostEditorPage() {
  const { hasSubscription } = useAuth();
  const { t } = useLang();
  const { postId } = useParams();
  const navigate = useNavigate();
  const [post, setPost] = useState(null);
  const [pages, setPages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [multiVariantEnabled, setMultiVariantEnabled] = useState(false);
  const [variantCount, setVariantCount] = useState(3);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  async function load() {
    setLoading(true);
    try {
      const [postData, pageData] = await Promise.all([apiRequest(`/posts/${postId}`), apiRequest("/pages")]);
      setPost({ ...postData, hashtags: (postData.hashtags || []).join(", ") });
      setPages(pageData);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [postId]);

  useEffect(() => {
    if (!message) return undefined;
    const timer = setTimeout(() => setMessage(""), 4000);
    return () => clearTimeout(timer);
  }, [message]);

  async function handleSave(event) {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      await apiRequest(`/posts/${postId}`, {
        method: "PUT",
        body: JSON.stringify({
          ...post,
          page_id: post.page_id ? Number(post.page_id) : null,
          hashtags: post.hashtags.split(",").map((item) => item.trim()).filter(Boolean)
        })
      });
      setMessage(t("editor.savedMsg"));
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  async function publishNow() {
    setError("");
    try {
      await apiRequest(`/posts/${postId}/publish`, { method: "POST" });
      setMessage(t("editor.publishRequestedMsg"));
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function generateIllustrations() {
    setError("");
    try {
      const requestedVariantCount = multiVariantEnabled ? Number(variantCount) : 1;
      await apiRequest(`/posts/${postId}/generate-image`, {
        method: "POST",
        body: JSON.stringify({ variant_count: requestedVariantCount })
      });
      setMessage(
        requestedVariantCount === 1
          ? t("editor.imageCreated")
          : t("editor.imagesCreated").replace("{count}", requestedVariantCount)
      );
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function createVisualBrief() {
    setError("");
    try {
      await apiRequest(`/posts/${postId}/visual-brief`, { method: "POST" });
      setMessage(t("editor.visualBriefCreated"));
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function deleteDraft() {
    const confirmed = window.confirm(t("editor.confirmDelete"));
    if (!confirmed) return;
    setError("");
    try {
      await apiRequest(`/posts/${postId}`, { method: "DELETE" });
      navigate("/posts");
    } catch (err) {
      setError(err.message);
    }
  }

  const canDelete = post && ["idea", "draft", "failed"].includes(post.status);

  if (loading) {
    return (
      <div className="full-screen-panel">
        <Spinner />
      </div>
    );
  }

  if (!post) {
    return (
      <div className="full-screen-panel">
        <p>{t("editor.notFound")}</p>
      </div>
    );
  }

  return (
    <div className="page-stack">
      <section className="hero-banner">
        <div>
          <div className="eyebrow">{t("editor.eyebrow")}</div>
          <h1>{post.title || t("common.noName")}</h1>
          <p>{t("editor.subtitle")}</p>
        </div>
        <div className="hero-actions">
          <StatusPill status={post.status} />
          <Link className="secondary-button" to="/studio">
            {t("editor.backToStudio")}
          </Link>
        </div>
      </section>

      {error && <div className="inline-error">{error}</div>}
      {message && <div className="inline-success">{message}</div>}

      <div className="two-column-layout">
        <Card title={t("editor.editPostTitle")} subtitle={t("editor.editPostSubtitle")} variant="glass">
          <div className="panel-note" style={{ marginBottom: "1rem" }}>
            {t("editor.imageNote")}
          </div>
          <div className="stack-blocks" style={{ marginBottom: "1rem" }}>
            <label style={{ display: "flex", alignItems: "center", gap: "0.65rem", fontWeight: 700 }}>
              <input
                type="checkbox"
                checked={multiVariantEnabled}
                onChange={(event) => setMultiVariantEnabled(event.target.checked)}
              />
              {t("editor.enableMultiVariants")}
            </label>
            {multiVariantEnabled ? (
              <label style={{ maxWidth: "220px" }}>
                {t("editor.variantCount")}
                <select value={variantCount} onChange={(event) => setVariantCount(Number(event.target.value))}>
                  <option value={2}>2 variants</option>
                  <option value={3}>3 variants</option>
                  <option value={4}>4 variants</option>
                </select>
              </label>
            ) : null}
          </div>
          <form className="stack-form" onSubmit={handleSave}>
            <label>
              {t("editor.postTitle")}
              <input value={post.title || ""} onChange={(event) => setPost({ ...post, title: event.target.value })} />
            </label>
            <label>
              Caption
              <textarea rows="12" value={post.caption || ""} onChange={(event) => setPost({ ...post, caption: event.target.value })} />
            </label>
            <div className="form-grid">
              <label>
                Content Pillar
                <input value={post.content_pillar || ""} onChange={(event) => setPost({ ...post, content_pillar: event.target.value })} />
              </label>
              <label>
                {t("editor.facebookPage")}
                <select value={post.page_id || ""} onChange={(event) => setPost({ ...post, page_id: event.target.value })}>
                  <option value="">{t("editor.notAssigned")}</option>
                  {pages.map((page) => (
                    <option key={page.id} value={page.id}>
                      {page.name}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <label>
              Hashtags
              <input
                value={post.hashtags || ""}
                onChange={(event) => setPost({ ...post, hashtags: event.target.value })}
                placeholder="#FlowPilot, #ContentAI"
              />
            </label>
            <label>
              Image Prompt
              <textarea rows="4" value={post.image_prompt || ""} onChange={(event) => setPost({ ...post, image_prompt: event.target.value })} />
            </label>
            <div className="button-row">
              <button className="primary-button" type="submit" disabled={saving || !hasSubscription}>
                {saving ? t("editor.saving") : t("editor.save")}
              </button>
              <button className="secondary-button" type="button" onClick={createVisualBrief} disabled={!hasSubscription}>
                {t("editor.createVisualBrief")}
              </button>
              <button className="secondary-button" type="button" onClick={generateIllustrations} disabled={!hasSubscription}>
                {multiVariantEnabled ? `Generate ${variantCount} Variants` : "Generate Image"}
              </button>
              {canDelete && (
                <button className="danger-button" type="button" onClick={deleteDraft} disabled={!hasSubscription}>
                  {t("editor.deleteDraft")}
                </button>
              )}
              {post.status === "approved" && (
                <button className="ghost-button" type="button" onClick={publishNow} disabled={!hasSubscription}>
                  {t("editor.publishNow")}
                </button>
              )}
            </div>
          </form>
        </Card>

        <Card title={t("editor.postMetadata")} subtitle={t("editor.postMetadataSubtitle")} variant="glass">
          <div className="stack-blocks">
            {post.assets?.length > 0 ? (
              <div className="three-col">
                {post.assets.map((asset) => (
                  <img
                    key={asset.id}
                    src={asset.asset_url}
                    alt={asset.alt_text || post.title}
                    style={{ width: "100%", borderRadius: "18px", border: "1px solid var(--line)" }}
                  />
                ))}
              </div>
            ) : (
              <div className="empty-state centered">
                <p>{t("editor.noImages")}</p>
              </div>
            )}
            <div className="surface-row">
              <span>{t("editor.imageAssets")}</span>
              <strong>{post.assets?.length ?? 0}</strong>
            </div>
            <div className="surface-row">
              <span>{t("editor.qualityScore")}</span>
              <strong>{post.quality_score ?? "-"}</strong>
            </div>
            <div className="surface-row">
              <span>{t("editor.approvedAt")}</span>
              <strong>{formatDate(post.approved_at)}</strong>
            </div>
            <div className="surface-row">
              <span>{t("editor.scheduledFor")}</span>
              <strong>{formatDate(post.scheduled_for)}</strong>
            </div>
            <div className="surface-row">
              <span>{t("editor.facebookPostId")}</span>
              <strong>{post.fb_post_id || "-"}</strong>
            </div>
            {post.last_error && <div className="inline-error">{t("editor.lastError")}: {post.last_error}</div>}
            <div className="button-row">
              <Link className="secondary-button" to={`/posts/${post.id}/schedule`}>
                Schedule
              </Link>
              <Link className="ghost-button" to="/publish-logs">
                {t("editor.viewLogs")}
              </Link>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}
