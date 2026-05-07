import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import Card from "../components/Card";
import Spinner from "../components/Spinner";
import StatusPill from "../components/StatusPill";
import { useAuth } from "../context/AuthContext";
import { useLang } from "../context/LangContext";
import { apiRequest } from "../services/api";

export default function ReviewQueuePage() {
  const { hasSubscription } = useAuth();
  const { t } = useLang();
  const [posts, setPosts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (message) {
      const timer = setTimeout(() => setMessage(""), 4000);
      return () => clearTimeout(timer);
    }
  }, [message]);

  function loadPosts() {
    setLoading(true);
    apiRequest("/posts")
      .then((data) =>
        setPosts(data.filter((post) => ["draft", "ready_for_review", "approved"].includes(post.status)))
      )
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    loadPosts();
  }, []);

  async function decide(postId, approved) {
    setError("");
    setActionLoading(postId);
    try {
      await apiRequest(`/posts/${postId}/approve`, {
        method: "POST",
        body: JSON.stringify({
          approved,
          notes: approved ? null : "ต้องการการปรับแก้เพิ่มเติม"
        })
      });
      setMessage(approved ? t("reviewQueue.approvedMsg") : t("reviewQueue.sentBackMsg"));
      loadPosts();
    } catch (err) {
      setError(err.message);
    } finally {
      setActionLoading(null);
    }
  }

  return (
    <div className="page-stack">
      <section className="hero-banner">
        <div>
          <p className="eyebrow">{t("reviewQueue.eyebrow")}</p>
          <h1>{t("reviewQueue.title")}</h1>
          <p>{t("reviewQueue.subtitle")}</p>
        </div>
      </section>

      {error && <div className="inline-error">{error}</div>}
      {message && <div className="inline-success">{message}</div>}

      {loading ? (
        <div className="loading-center">
          <Spinner />
        </div>
      ) : posts.length === 0 ? (
        <Card>
          <div className="empty-state">
            <p>{t("reviewQueue.noPostsPending")}</p>
            <p>{t("reviewQueue.noPostsHint")}</p>
          </div>
        </Card>
      ) : (
        <div className="review-list">
          {posts.map((post) => (
            <article className="review-item card" key={post.id}>
              <div>
                <div className="review-headline">
                  <h3>{post.title}</h3>
                  <StatusPill status={post.status} />
                </div>
                {post.content_pillar && (
                  <p className="muted-label" style={{ fontSize: "0.82rem", marginTop: "0.2rem" }}>
                    {post.content_pillar}
                  </p>
                )}
              </div>

              <p className="preview-copy" style={{ fontSize: "0.92rem" }}>
                {post.caption || t("reviewQueue.noCaption")}
              </p>

              {post.hashtags?.length > 0 && (
                <p className="muted-label" style={{ fontSize: "0.82rem" }}>
                  {post.hashtags.join(" ")}
                </p>
              )}

              <div className="button-row">
                {post.status !== "approved" && (
                  <button
                    className="primary-button"
                    type="button"
                    onClick={() => decide(post.id, true)}
                    disabled={actionLoading === post.id || !hasSubscription}
                  >
                    {actionLoading === post.id ? <Spinner size="sm" /> : t("reviewQueue.approve")}
                  </button>
                )}
                {post.status === "approved" && (
                  <Link className="primary-button" to={`/posts/${post.id}/schedule`}>
                    {t("reviewQueue.scheduleLink")}
                  </Link>
                )}
                <button
                  className="secondary-button"
                  type="button"
                  onClick={() => decide(post.id, false)}
                  disabled={actionLoading === post.id || !hasSubscription}
                >
                  {t("reviewQueue.sendBack")}
                </button>
                <Link className="ghost-button" to={`/posts/${post.id}/edit`}>
                  {t("reviewQueue.edit")}
                </Link>
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
