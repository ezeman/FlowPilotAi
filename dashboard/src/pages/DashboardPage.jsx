import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import Card from "../components/Card";
import Spinner from "../components/Spinner";
import StatusPill from "../components/StatusPill";
import { useAuth } from "../context/AuthContext";
import { useLang } from "../context/LangContext";
import { apiRequest } from "../services/api";
import { isPlatformOwner } from "../utils/roles";

const PIPELINE_STEPS = ["idea", "draft", "ready_for_review", "approved", "scheduled", "posted"];

const STATUS_LABELS = {
  idea: "Brief",
  draft: "Draft",
  ready_for_review: "Review",
  approved: "Approved",
  scheduled: "Scheduled",
  posted: "Posted"
};

function formatDate(iso) {
  if (!iso) return "-";
  return new Date(iso).toLocaleString("th-TH", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit"
  });
}

export default function DashboardPage() {
  const { user } = useAuth();
  const { t } = useLang();
  const platformOwner = isPlatformOwner(user);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    apiRequest("/dashboard/summary")
      .then(setSummary)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  const pendingReview = summary?.post_status_counts?.ready_for_review || 0;
  const failedCount = summary?.failed_publishes || 0;

  return (
    <div className="page-stack">
      <section className="hero-banner">
        <div>
          <div className="eyebrow">{t("dashboard.eyebrow")}</div>
          <h1>{t("dashboard.title")}</h1>
          <p>{t("dashboard.subtitle")}</p>
          <div className="workflow-pipeline">
            {PIPELINE_STEPS.map((step) => (
              <span key={step} className="pipeline-step">
                {STATUS_LABELS[step]}
              </span>
            ))}
          </div>
        </div>
        <div className="hero-actions">
          {platformOwner ? (
            <>
              <Link className="primary-button" to="/settings">Manage Accounts</Link>
              <Link className="secondary-button" to="/billing">Review Payments</Link>
            </>
          ) : (
            <>
              <Link className="primary-button" to="/studio">
                {t("dashboard.openStudio")}
              </Link>
              <Link className="secondary-button" to="/posts">
                {t("dashboard.viewAllPosts")}
              </Link>
            </>
          )}
        </div>
      </section>

      {error && <div className="inline-error">{error}</div>}

      {loading ? (
        <div className="loading-center">
          <Spinner />
        </div>
      ) : (
        <>
          {!platformOwner && (pendingReview > 0 || failedCount > 0) && (
            <div className="alerts-stack">
              {pendingReview > 0 && (
                <div className="alert-box alert-info">
                  <span>{t("dashboard.alertPendingReview").replace("{count}", pendingReview)}</span>
                  <Link className="primary-button" to="/review-queue">
                    {t("dashboard.alertGoReviewer")}
                  </Link>
                </div>
              )}
              {failedCount > 0 && (
                <div className="alert-box alert-warning">
                  <span>{t("dashboard.alertFailedPublish").replace("{count}", failedCount)}</span>
                  <Link className="ghost-button" to="/publish-logs">
                    {t("dashboard.alertOpenLogs")}
                  </Link>
                </div>
              )}
            </div>
          )}

          <div className="stats-grid">
            <div className="stat-card">
              <div className="stat-label">{t("dashboard.upcoming")}</div>
              <div className="stat-value">{summary?.upcoming_posts ?? 0}</div>
              <p className="metric-caption">{t("dashboard.upcomingCaption")}</p>
            </div>
            <div className="stat-card">
              <div className="stat-label">{t("dashboard.draftReview")}</div>
              <div className="stat-value">
                {(summary?.post_status_counts?.draft || 0) + (summary?.post_status_counts?.ready_for_review || 0)}
              </div>
              <p className="metric-caption">{t("dashboard.draftReviewCaption")}</p>
            </div>
            <div className="stat-card">
              <div className="stat-label">{t("dashboard.published")}</div>
              <div className="stat-value">{summary?.post_status_counts?.posted ?? 0}</div>
              <p className="metric-caption">{t("dashboard.publishedCaption")}</p>
            </div>
            <div className="stat-card">
              <div className="stat-label">{t("dashboard.failures")}</div>
              <div className="stat-value" style={{ color: failedCount ? "var(--danger)" : undefined }}>
                {failedCount}
              </div>
              <p className="metric-caption">{t("dashboard.failuresCaption")}</p>
            </div>
          </div>

          {!platformOwner && <div className="two-column-layout">
            <Card
              title={t("dashboard.quickActions")}
              subtitle={t("dashboard.quickActionsSubtitle")}
              actions={<Link className="ghost-button" to="/calendar">{t("dashboard.openCalendar")}</Link>}
            >
              <div className="stack-blocks">
                <div className="surface-panel" style={{ padding: "1rem" }}>
                  <strong>{t("dashboard.strategistTitle")}</strong>
                  <p>{t("dashboard.strategistDesc")}</p>
                  <div className="button-row" style={{ marginTop: "0.8rem" }}>
                    <Link className="primary-button" to="/studio">
                      {t("dashboard.createBrief")}
                    </Link>
                  </div>
                </div>
                <div className="surface-panel" style={{ padding: "1rem" }}>
                  <strong>{t("dashboard.publisherTitle")}</strong>
                  <p>{t("dashboard.publisherDesc")}</p>
                  <div className="button-row" style={{ marginTop: "0.8rem" }}>
                    <Link className="secondary-button" to="/studio">
                      {t("dashboard.goPublisher")}
                    </Link>
                  </div>
                </div>
              </div>
            </Card>

            <Card title={t("dashboard.pipelineStatus")} subtitle={t("dashboard.pipelineSubtitle")}>
              <div className="pill-cloud">
                {Object.entries(summary?.post_status_counts || {}).map(([status, count]) => (
                  <div key={status} className="surface-row">
                    <StatusPill status={status} />
                    <strong>{count}</strong>
                  </div>
                ))}
              </div>
            </Card>
          </div>}

          <Card title={t("dashboard.recentLogs")} subtitle={t("dashboard.recentLogsSubtitle")}>
            {(summary?.latest_publish_logs || []).length === 0 ? (
              <div className="empty-state centered">
                <p>{t("dashboard.noLogs")}</p>
              </div>
            ) : (
              <div className="table-shell">
                <table>
                  <thead>
                    <tr>
                      <th>{t("dashboard.tablePost")}</th>
                      <th>{t("dashboard.tableStatus")}</th>
                      <th>{t("dashboard.tableFbId")}</th>
                      <th>{t("dashboard.tableTime")}</th>
                      <th>{t("dashboard.tableError")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {summary.latest_publish_logs.map((log) => (
                      <tr key={log.id}>
                        <td>
                          {platformOwner ? (
                            <strong>#{log.post_id}</strong>
                          ) : (
                            <Link to={`/posts/${log.post_id}/edit`} style={{ color: "var(--primary)", fontWeight: 700 }}>
                              #{log.post_id}
                            </Link>
                          )}
                        </td>
                        <td>
                          <StatusPill status={log.status} />
                        </td>
                        <td>{log.fb_post_id || "-"}</td>
                        <td>{formatDate(log.created_at)}</td>
                        <td style={{ color: log.error_message ? "var(--danger)" : "var(--text-muted)" }}>
                          {log.error_message || "-"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </>
      )}
    </div>
  );
}
