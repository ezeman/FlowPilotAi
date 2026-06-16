import { useEffect, useState } from "react";

import Card from "../components/Card";
import Spinner from "../components/Spinner";
import { useAuth } from "../context/AuthContext";
import { useLang } from "../context/LangContext";
import { apiRequest } from "../services/api";
import { isPlatformOwner } from "../utils/roles";

const BANK_INFO = {
  bank_transfer: {
    key: "bankTransfer",
    lines: [
      { key: "bankInfoKBank" },
      { key: "bankInfoAccount" },
      { key: "bankInfoName" },
    ],
  },
  promptpay: {
    key: "promptPay",
    lines: [
      { key: "promptPayNumber" },
      { key: "promptPayName" },
    ],
  },
};

const emptyForm = {
  payment_method: "bank_transfer",
  bank_name: "",
  reference_number: "",
  transfer_date: "",
  note: "",
};

function StatusBadge({ status, t }) {
  const STATUS_COLOR = {
    pending: { bg: "#e67e22", labelKey: "pendingStatus" },
    approved: { bg: "#27ae60", labelKey: "approvedStatus" },
    rejected: { bg: "#c0392b", labelKey: "rejectedStatus" },
  };
  const s = STATUS_COLOR[status] || { bg: "#888", labelKey: null };
  return (
    <span className="status-pill" style={{ background: s.bg, color: "#fff" }}>
      {s.labelKey ? t(`billing.${s.labelKey}`) : status}
    </span>
  );
}

export default function BillingPage() {
  const { user } = useAuth();
  const { t } = useLang();
  const isSubscriberAdmin = user?.role === "subscriber_admin";
  const isPlatformAdmin = isPlatformOwner(user);

  const [loading, setLoading] = useState(true);
  const [plans, setPlans] = useState([]);
  const [subscription, setSubscription] = useState(null);
  const [requests, setRequests] = useState([]);
  const [selectedPlan, setSelectedPlan] = useState(null);
  const [form, setForm] = useState(emptyForm);
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [rejectForms, setRejectForms] = useState({});
  const [processingRequestId, setProcessingRequestId] = useState(null);

  async function loadData() {
    setLoading(true);
    try {
      const [plansData, subData, reqData] = await Promise.all([
        apiRequest("/accounts/plans"),
        apiRequest("/accounts/me/subscription").catch(() => null),
        (isSubscriberAdmin || isPlatformAdmin) ? apiRequest("/billing/payment-requests") : Promise.resolve([]),
      ]);
      setPlans(plansData);
      setSubscription(subData);
      setRequests(reqData);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function approvePayment(requestId) {
    setProcessingRequestId(requestId);
    setError("");
    try {
      await apiRequest(`/billing/payment-requests/${requestId}/approve`, { method: "POST" });
      setMessage("Payment request approved.");
      await loadData();
    } catch (err) {
      setError(err.message);
    } finally {
      setProcessingRequestId(null);
    }
  }

  async function rejectPayment(requestId) {
    const reason = rejectForms[requestId]?.trim();
    if (!reason) {
      setError("Rejection reason is required.");
      return;
    }
    setProcessingRequestId(requestId);
    setError("");
    try {
      await apiRequest(`/billing/payment-requests/${requestId}/reject`, {
        method: "POST",
        body: JSON.stringify({ reason }),
      });
      setMessage("Payment request rejected.");
      setRejectForms((current) => {
        const next = { ...current };
        delete next[requestId];
        return next;
      });
      await loadData();
    } catch (err) {
      setError(err.message);
    } finally {
      setProcessingRequestId(null);
    }
  }

  useEffect(() => {
    loadData();
  }, []);

  useEffect(() => {
    if (!message) return undefined;
    const timer = setTimeout(() => setMessage(""), 5000);
    return () => clearTimeout(timer);
  }, [message]);

  function field(key) {
    return (e) => setForm((prev) => ({ ...prev, [key]: e.target.value }));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (!selectedPlan) return;
    setSubmitting(true);
    setError("");
    try {
      await apiRequest("/billing/payment-requests", {
        method: "POST",
        body: JSON.stringify({
          plan_code: selectedPlan.code,
          payment_method: form.payment_method,
          bank_name: form.bank_name || null,
          reference_number: form.reference_number || null,
          transfer_date: form.transfer_date || null,
          note: form.note || null,
        }),
      });
      setMessage(t("billing.successMsg"));
      setSelectedPlan(null);
      setForm(emptyForm);
      await loadData();
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  const activePlan = subscription?.plan;
  const hasPending = requests.some((r) => r.status === "pending");

  return (
    <div className="page-stack">
      <section className="hero-banner">
        <div>
          <div className="eyebrow">{t("billing.eyebrow")}</div>
          <h1>{t("billing.title")}</h1>
          <p>{t("billing.subtitle")}</p>
        </div>
      </section>

      {error && <div className="inline-error">{error}</div>}
      {message && <div className="inline-success">{message}</div>}

      {loading ? (
        <div className="loading-center"><Spinner /></div>
      ) : (
        <>
          <Card title={t("billing.currentPlan")} variant="glass">
            {activePlan ? (
              <div className="surface-row">
                <div>
                  <strong style={{ fontSize: "1.1rem" }}>{activePlan.name}</strong>
                  <p>฿{activePlan.price_monthly.toLocaleString()} {t("billing.perMonth")} · {activePlan.max_pages} pages · {activePlan.max_users} users</p>
                </div>
                <span className="status-pill" style={{ background: "var(--primary)", color: "#fff" }}>{t("billing.activeBadge")}</span>
              </div>
            ) : (
              <p style={{ color: "var(--text-muted)" }}>{t("billing.noPlan")}</p>
            )}
          </Card>

          {isSubscriberAdmin && !hasPending && (
            <div>
              <h2 style={{ marginBottom: "1rem" }}>{t("billing.selectPlan")}</h2>
              <div className="two-column-layout" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))" }}>
                {plans.map((plan) => (
                  <div
                    key={plan.code}
                    className="surface-panel"
                    style={{
                      padding: "1.25rem",
                      cursor: "pointer",
                      border: selectedPlan?.code === plan.code ? "2px solid var(--primary)" : "2px solid transparent",
                      borderRadius: "0.75rem",
                    }}
                    onClick={() => setSelectedPlan(plan)}
                  >
                    <strong style={{ fontSize: "1.05rem" }}>{plan.name}</strong>
                    <p style={{ fontSize: "1.4rem", fontWeight: 700, margin: "0.4rem 0", color: "var(--primary)" }}>
                      ฿{plan.price_monthly.toLocaleString()}
                      <span style={{ fontSize: "0.8rem", fontWeight: 400, color: "var(--text-muted)" }}> {t("billing.perMonth")}</span>
                    </p>
                    <div style={{ fontSize: "0.84rem", color: "var(--text-muted)", display: "flex", flexDirection: "column", gap: "0.2rem" }}>
                      <span>{t("billing.pages")} {plan.max_pages}</span>
                      <span>{t("billing.users")} {plan.max_users}</span>
                      <span>{t("billing.autoIdeasPerDay")} {plan.max_auto_ideas_per_day}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {hasPending && isSubscriberAdmin && (
            <Card variant="glass">
              <p style={{ color: "var(--text-muted)" }}>{t("billing.pendingRequest")}</p>
            </Card>
          )}

          {selectedPlan && isSubscriberAdmin && (
            <Card title={`${t("billing.paymentTitle")} — ${selectedPlan.name} (฿${selectedPlan.price_monthly.toLocaleString()})`} variant="glass">
              <div className="two-column-layout">
                <div>
                  <p style={{ fontWeight: 600, marginBottom: "0.5rem" }}>{t("billing.bankInfo")}</p>
                  <label style={{ display: "block", marginBottom: "0.5rem" }}>
                    {t("billing.paymentMethod")}
                    <select value={form.payment_method} onChange={field("payment_method")} style={{ display: "block", marginTop: "0.25rem" }}>
                      <option value="bank_transfer">{t("billing.bankTransfer")}</option>
                      <option value="promptpay">{t("billing.promptPay")}</option>
                    </select>
                  </label>
                  <div className="surface-panel" style={{ padding: "0.75rem", fontSize: "0.86rem", lineHeight: 1.7 }}>
                    {BANK_INFO[form.payment_method]?.lines.map((line) => (
                      <div key={line.key}>{t(`billing.${line.key}`)}</div>
                    ))}
                  </div>
                </div>

                <form className="stack-form" onSubmit={handleSubmit}>
                  {form.payment_method === "bank_transfer" && (
                    <label>
                      {t("billing.bankName")}
                      <input value={form.bank_name} onChange={field("bank_name")} placeholder={t("billing.bankNamePlaceholder")} />
                    </label>
                  )}
                  <label>
                    {t("billing.referenceNumber")}
                    <input value={form.reference_number} onChange={field("reference_number")} placeholder={t("billing.referenceNumberPlaceholder")} />
                  </label>
                  <label>
                    {t("billing.transferDate")}
                    <input type="date" value={form.transfer_date} onChange={field("transfer_date")} />
                  </label>
                  <label>
                    {t("billing.note")}
                    <textarea rows="2" value={form.note} onChange={field("note")} placeholder={t("billing.notePlaceholder")} />
                  </label>
                  <div className="button-row">
                    <button className="primary-button" type="submit" disabled={submitting}>
                      {submitting ? t("billing.submitting") : t("billing.submit")}
                    </button>
                    <button className="secondary-button" type="button" onClick={() => setSelectedPlan(null)}>
                      {t("billing.cancel")}
                    </button>
                  </div>
                </form>
              </div>
            </Card>
          )}

          {requests.length > 0 && (
            <Card title={t("billing.paymentHistory")} variant="glass">
              <div className="stack-blocks">
                {requests.map((req) => (
                  <div key={req.id} className="surface-row">
                    <div>
                      <strong>{req.plan_code} — ฿{req.amount.toLocaleString()}</strong>
                      {isPlatformAdmin && <p>{req.account_name || `Account #${req.account_id}`}</p>}
                      <p>{req.payment_method === "promptpay" ? t("billing.promptPay") : t("billing.bankTransfer")}{req.bank_name ? ` (${req.bank_name})` : ""}</p>
                      {req.reference_number && <p>{t("billing.ref")} {req.reference_number}</p>}
                      {req.transfer_date && <p>{t("billing.transferDateLabel")} {req.transfer_date}</p>}
                      {req.reject_reason && <p style={{ color: "#c0392b" }}>{t("billing.rejectReason")} {req.reject_reason}</p>}
                      <p style={{ color: "var(--text-muted)", fontSize: "0.8rem" }}>
                        {new Date(req.created_at).toLocaleDateString("th-TH")}
                      </p>
                    </div>
                    <StatusBadge status={req.status} t={t} />
                    {isPlatformAdmin && req.status === "pending" && (
                      <div className="button-row" style={{ justifyContent: "flex-end", minWidth: "260px" }}>
                        <button
                          className="primary-button"
                          type="button"
                          disabled={processingRequestId === req.id}
                          onClick={() => approvePayment(req.id)}
                        >
                          {processingRequestId === req.id ? "Processing..." : "Approve"}
                        </button>
                        <input
                          placeholder="Reject reason"
                          value={rejectForms[req.id] || ""}
                          onChange={(event) => setRejectForms((current) => ({ ...current, [req.id]: event.target.value }))}
                          style={{ minWidth: "160px" }}
                        />
                        <button
                          className="secondary-button"
                          type="button"
                          disabled={processingRequestId === req.id || !rejectForms[req.id]?.trim()}
                          onClick={() => rejectPayment(req.id)}
                        >
                          Reject
                        </button>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
