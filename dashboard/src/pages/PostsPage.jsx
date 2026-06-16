import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

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
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit"
  });
}

function canDelete(item) {
  return item.kind === "post" && ["idea", "draft", "failed"].includes(item.status);
}

export default function PostsPage() {
  const { hasSubscription } = useAuth();
  const { t } = useLang();
  const subscriptionMessage = "Your account does not have an active subscription. Please submit a payment request from Billing.";
  const [posts, setPosts] = useState([]);
  const [calendarItems, setCalendarItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [activeStatus, setActiveStatus] = useState("");
  const [deletingId, setDeletingId] = useState(null);

  const ALL_STATUSES = [
    { value: "", label: t("posts.all") },
    { value: "idea", label: t("status.idea") },
    { value: "draft", label: t("status.draft") },
    { value: "ready_for_review", label: t("status.ready_for_review") },
    { value: "approved", label: t("status.approved") },
    { value: "scheduled", label: t("status.scheduled") },
    { value: "posted", label: t("status.posted") },
    { value: "failed", label: t("status.failed") }
  ];

  async function loadLibrary() {
    setLoading(true);
    try {
      const [postsData, calendarData] = await Promise.all([
        apiRequest("/posts"),
        apiRequest("/content-calendar")
      ]);
      setPosts(postsData);
      setCalendarItems(calendarData);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadLibrary();
  }, []);

  useEffect(() => {
    if (!message) return undefined;
    const timer = setTimeout(() => setMessage(""), 3500);
    return () => clearTimeout(timer);
  }, [message]);

  const libraryItems = useMemo(() => {
    const linkedCalendarIds = new Set(posts.map((post) => post.calendar_id).filter(Boolean));

    const postRows = posts.map((post) => ({
      id: `post-${post.id}`,
      entityId: post.id,
      kind: "post",
      title: post.title,
      status: post.status,
      content_pillar: post.content_pillar,
      updated_at: post.updated_at,
      to: `/posts/${post.id}/edit`,
      primaryAction: t("posts.editAction")
    }));

    const ideaRows = calendarItems
      .filter((item) => item.status === "idea" && !linkedCalendarIds.has(item.id))
      .map((item) => ({
        id: `calendar-${item.id}`,
        entityId: item.id,
        kind: "calendar",
        title: item.title,
        status: "idea",
        content_pillar: item.content_pillar,
        updated_at: item.updated_at,
        to: `/studio?calendar_id=${item.id}`,
        primaryAction: t("posts.openInStudio")
      }));

    return [...ideaRows, ...postRows].sort(
      (left, right) => new Date(right.updated_at) - new Date(left.updated_at)
    );
  }, [posts, calendarItems]);

  const counts = useMemo(
    () =>
      ALL_STATUSES.reduce((accumulator, item) => {
        accumulator[item.value] = item.value
          ? libraryItems.filter((entry) => entry.status === item.value).length
          : libraryItems.length;
        return accumulator;
      }, {}),
    [libraryItems]
  );

  const filteredItems = activeStatus
    ? libraryItems.filter((entry) => entry.status === activeStatus)
    : libraryItems;

  async function deleteDraft(postId) {
    if (!hasSubscription) {
      setError(subscriptionMessage);
      return;
    }
    const confirmed = window.confirm(t("posts.confirmDelete"));
    if (!confirmed) return;
    setDeletingId(postId);
    setError("");
    try {
      await apiRequest(`/posts/${postId}`, { method: "DELETE" });
      setPosts((current) => current.filter((post) => post.id !== postId));
      setMessage(t("posts.deleted"));
    } catch (err) {
      setError(err.message);
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <div className="page-stack">
      <section className="hero-banner">
        <div>
          <div className="eyebrow">{t("posts.eyebrow")}</div>
          <h1>{t("posts.title")}</h1>
          <p>{t("posts.subtitle")}</p>
        </div>
        <div className="hero-actions">
          {hasSubscription ? (
            <Link className="primary-button" to="/studio">
              {t("posts.openStudio")}
            </Link>
          ) : (
            <button className="primary-button" type="button" disabled title={subscriptionMessage}>
              {t("posts.openStudio")}
            </button>
          )}
        </div>
      </section>

      <Card title={t("posts.contentQueue")} subtitle={t("posts.contentQueueSubtitle")} variant="glass">
        <div className="tab-bar">
          {ALL_STATUSES.map((item) => (
            <button
              key={item.value}
              type="button"
              className={`tab-btn${activeStatus === item.value ? " active" : ""}`}
              onClick={() => setActiveStatus(item.value)}
            >
              {item.label}
              <span className="tab-count">{counts[item.value] || 0}</span>
            </button>
          ))}
        </div>

        {error && <div className="inline-error" style={{ marginTop: "1rem" }}>{error}</div>}
        {!hasSubscription && (
          <div className="subscription-warning" style={{ marginTop: "1rem" }}>
            <div>
              <strong>{subscriptionMessage}</strong>
            </div>
            <Link className="primary-button" to="/billing">Billing</Link>
          </div>
        )}
        {message && <div className="inline-success" style={{ marginTop: "1rem" }}>{message}</div>}

        {loading ? (
          <div className="loading-center">
            <Spinner />
          </div>
        ) : filteredItems.length === 0 ? (
          <div className="empty-state centered">
            <p>{t("common.noItems")}</p>
          </div>
        ) : (
          <div className="posts-list" style={{ marginTop: "1rem" }}>
            {filteredItems.map((item) => (
              <div key={item.id} className="post-item">
                <div className="post-item-info">
                  <div className="post-item-title">{item.title || t("common.noName")}</div>
                  <div className="post-item-meta">
                    {item.content_pillar || t("common.uncategorized")} · {item.kind === "calendar" ? t("posts.calendarIdea") : t("posts.post")} · {t("common.updated")} {formatDate(item.updated_at)}
                  </div>
                </div>
                <StatusPill status={item.status} />
                <div className="button-row">
                  {hasSubscription ? (
                    <Link className="ghost-button" to={item.to}>
                      {item.primaryAction}
                    </Link>
                  ) : (
                    <button className="ghost-button" type="button" disabled title={subscriptionMessage}>
                      {item.primaryAction}
                    </button>
                  )}
                  {item.kind === "post" && item.status === "approved" && (
                    hasSubscription ? (
                      <Link className="secondary-button" to={`/posts/${item.entityId}/schedule`}>
                        Schedule
                      </Link>
                    ) : (
                      <button className="secondary-button" type="button" disabled title={subscriptionMessage}>
                        Schedule
                      </button>
                    )
                  )}
                  {canDelete(item) && (
                    <button
                      className="danger-button"
                      type="button"
                      onClick={() => deleteDraft(item.entityId)}
                      disabled={deletingId === item.entityId || !hasSubscription}
                      title={!hasSubscription ? subscriptionMessage : undefined}
                    >
                      {deletingId === item.entityId ? t("common.deleting") : t("common.delete")}
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
