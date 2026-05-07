import { useEffect, useMemo, useState } from "react";

import Card from "../components/Card";
import Spinner from "../components/Spinner";
import { useAuth } from "../context/AuthContext";
import { useLang } from "../context/LangContext";
import { apiRequest } from "../services/api";

const emptySettingForm = {
  key: "openai_api_key",
  value_text: "",
  description: ""
};

const defaultScheduleForm = {
  enabled: false,
  time_local: "09:00",
  count: 5
};

const defaultAccountForm = {
  name: "",
  slug: "",
  plan_code: "starter"
};

const defaultUserForm = {
  email: "",
  full_name: "",
  password: "",
  role: "editor",
  account_id: "",
};

const SUBSCRIBER_KEYS = [
  { value: "default_tone", label: "Default Tone" },
  { value: "content_pillars", label: "Content Pillars (JSON)" }
];

const PLATFORM_KEYS = [
  { value: "openai_api_key", label: "OpenAI API Key" },
  ...SUBSCRIBER_KEYS,
];

function slugify(value) {
  return value
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

export default function SettingsPage() {
  const { user, activeAccountId } = useAuth();
  const { t } = useLang();
  const isPlatformAdmin = user?.role === "platform_admin";
  const canManageAccountUsers = user?.role === "subscriber_admin" || isPlatformAdmin;
  const canManageSettings = user?.role === "subscriber_admin" || isPlatformAdmin;

  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const [settings, setSettings] = useState([]);
  const [pages, setPages] = useState([]);
  const [users, setUsers] = useState([]);
  const [accounts, setAccounts] = useState([]);
  const [plans, setPlans] = useState([]);
  const [subscription, setSubscription] = useState(null);
  const [paymentRequests, setPaymentRequests] = useState([]);
  const [rejectForms, setRejectForms] = useState({});
  const [processingRequestId, setProcessingRequestId] = useState(null);
  const [scheduleForm, setScheduleForm] = useState(defaultScheduleForm);
  const [scheduleState, setScheduleState] = useState({ last_run_local_date: null });

  const [settingForm, setSettingForm] = useState(emptySettingForm);
  const [pageForm, setPageForm] = useState({
    account_id: "",
    name: "",
    facebook_page_id: "",
    page_category: "Education",
    description: "",
    is_active: true,
    access_token: ""
  });
  const [accountForm, setAccountForm] = useState(defaultAccountForm);
  const [userForm, setUserForm] = useState(defaultUserForm);
  const [subscriptionForms, setSubscriptionForms] = useState({});

  const [savingSetting, setSavingSetting] = useState(false);
  const [deletingSettingId, setDeletingSettingId] = useState(null);
  const [savingPage, setSavingPage] = useState(false);
  const [savingSchedule, setSavingSchedule] = useState(false);
  const [runningSchedule, setRunningSchedule] = useState(false);
  const [savingAccount, setSavingAccount] = useState(false);
  const [savingUser, setSavingUser] = useState(false);
  const [updatingUserId, setUpdatingUserId] = useState(null);
  const [savingSubscriptionFor, setSavingSubscriptionFor] = useState(null);

  const accountMap = useMemo(() => new Map(accounts.map((account) => [account.id, account])), [accounts]);
  const currentAccount = useMemo(
    () => accounts.find((account) => String(account.id) === String(activeAccountId || user?.active_account_id || user?.account_id)) || user?.account || null,
    [accounts, activeAccountId, user]
  );
  const currentPlan = subscription?.plan || currentAccount?.active_subscription?.plan || null;
  const currentUsage = currentAccount?.usage || null;

  async function loadData() {
    setLoading(true);
    try {
      const requests = [
        apiRequest("/settings"),
        apiRequest("/pages"),
        apiRequest("/content-calendar/auto-ideas/schedule"),
        apiRequest("/users"),
        apiRequest("/accounts"),
        apiRequest("/accounts/plans"),
        apiRequest("/accounts/me/subscription"),
        isPlatformAdmin ? apiRequest("/billing/payment-requests") : Promise.resolve([]),
      ];
      const [settingsData, pagesData, scheduleData, usersData, accountsData, plansData, subscriptionData, paymentReqData] = await Promise.all(requests);

      setSettings(settingsData);
      setPages(pagesData);
      setUsers(usersData);
      setAccounts(accountsData);
      setPlans(plansData);
      setSubscription(subscriptionData);
      setPaymentRequests(paymentReqData || []);
      setScheduleForm(scheduleData.config);
      setScheduleState(scheduleData.state || { last_run_local_date: null });

      const preferredAccountId = activeAccountId || user?.active_account_id || user?.account_id || accountsData[0]?.id || "";
      const defaultAccountId = String(preferredAccountId);
      setPageForm((current) => ({ ...current, account_id: current.account_id || defaultAccountId }));
      setUserForm((current) => ({ ...current, account_id: current.account_id || defaultAccountId }));
      setSubscriptionForms(
        Object.fromEntries(
          accountsData.map((account) => [
            account.id,
            {
              plan_code: account.active_subscription?.plan?.code || plansData[0]?.code || "starter",
              status: account.active_subscription?.status || "active",
              auto_renew: Boolean(account.active_subscription?.auto_renew)
            }
          ])
        )
      );
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
    const timer = setTimeout(() => setMessage(""), 4000);
    return () => clearTimeout(timer);
  }, [message]);

  async function deleteSetting(settingId) {
    setDeletingSettingId(settingId);
    setError("");
    try {
      await apiRequest(`/settings/${settingId}`, { method: "DELETE" });
      setMessage(t("settings.deletedSetting"));
      await loadData();
    } catch (err) {
      setError(err.message);
    } finally {
      setDeletingSettingId(null);
    }
  }

  async function saveSetting(event) {
    event.preventDefault();
    setSavingSetting(true);
    setError("");
    try {
      await apiRequest("/settings", {
        method: "PUT",
        body: JSON.stringify(settingForm)
      });
      setSettingForm(emptySettingForm);
      setMessage(t("settings.savedAccountSetting"));
      await loadData();
    } catch (err) {
      setError(err.message);
    } finally {
      setSavingSetting(false);
    }
  }

  async function savePage(event) {
    event.preventDefault();
    setSavingPage(true);
    setError("");
    try {
      await apiRequest("/pages", {
        method: "POST",
        body: JSON.stringify({
          ...pageForm,
          account_id: pageForm.account_id ? Number(pageForm.account_id) : null
        })
      });
      setPageForm((current) => ({
        ...current,
        name: "",
        facebook_page_id: "",
        description: "",
        access_token: ""
      }));
      setMessage(t("settings.savedFacebookPage"));
      await loadData();
    } catch (err) {
      setError(err.message);
    } finally {
      setSavingPage(false);
    }
  }

  async function saveSchedule(event) {
    event.preventDefault();
    setSavingSchedule(true);
    setError("");
    try {
      const result = await apiRequest("/content-calendar/auto-ideas/schedule", {
        method: "PUT",
        body: JSON.stringify({
          enabled: scheduleForm.enabled,
          time_local: scheduleForm.time_local,
          count: Number(scheduleForm.count)
        })
      });
      setScheduleForm(result.config);
      setScheduleState(result.state);
      setMessage(t("settings.savedAutoSchedule"));
    } catch (err) {
      setError(err.message);
    } finally {
      setSavingSchedule(false);
    }
  }

  async function runScheduleNow() {
    setRunningSchedule(true);
    setError("");
    try {
      await apiRequest("/content-calendar/auto-ideas/run", { method: "POST" });
      setMessage(t("settings.queuedAutoGeneration"));
    } catch (err) {
      setError(err.message);
    } finally {
      setRunningSchedule(false);
    }
  }

  async function createAccount(event) {
    event.preventDefault();
    setSavingAccount(true);
    setError("");
    try {
      await apiRequest("/accounts", {
        method: "POST",
        body: JSON.stringify(accountForm)
      });
      setAccountForm(defaultAccountForm);
      setMessage(t("settings.createdAccount"));
      await loadData();
    } catch (err) {
      setError(err.message);
    } finally {
      setSavingAccount(false);
    }
  }

  async function createUser(event) {
    event.preventDefault();
    setSavingUser(true);
    setError("");
    try {
      await apiRequest("/users", {
        method: "POST",
        body: JSON.stringify({
          ...userForm,
          account_id: userForm.account_id ? Number(userForm.account_id) : null
        })
      });
      setUserForm((current) => ({
        ...current,
        email: "",
        full_name: "",
        password: ""
      }));
      setMessage(t("settings.createdUser"));
      await loadData();
    } catch (err) {
      setError(err.message);
    } finally {
      setSavingUser(false);
    }
  }

  async function updateUser(userId, patch) {
    setUpdatingUserId(userId);
    setError("");
    try {
      await apiRequest(`/users/${userId}`, { method: "PUT", body: JSON.stringify(patch) });
      setMessage(t("settings.updatedUser"));
      await loadData();
    } catch (err) {
      setError(err.message);
    } finally {
      setUpdatingUserId(null);
    }
  }

  async function approvePayment(requestId) {
    setProcessingRequestId(requestId);
    setError("");
    try {
      await apiRequest(`/billing/payment-requests/${requestId}/approve`, { method: "POST" });
      setMessage(t("settings.paymentApproved"));
      await loadData();
    } catch (err) {
      setError(err.message);
    } finally {
      setProcessingRequestId(null);
    }
  }

  async function rejectPayment(requestId) {
    const reason = rejectForms[requestId];
    if (!reason?.trim()) { setError(t("settings.rejectReasonRequired")); return; }
    setProcessingRequestId(requestId);
    setError("");
    try {
      await apiRequest(`/billing/payment-requests/${requestId}/reject`, { method: "POST", body: JSON.stringify({ reason }) });
      setMessage(t("settings.paymentRejected"));
      setRejectForms((prev) => { const next = { ...prev }; delete next[requestId]; return next; });
      await loadData();
    } catch (err) {
      setError(err.message);
    } finally {
      setProcessingRequestId(null);
    }
  }

  async function verifyUser(userId) {
    setUpdatingUserId(userId);
    setError("");
    try {
      await apiRequest(`/users/${userId}/verify`, { method: "POST" });
      setMessage(t("settings.userVerified"));
      await loadData();
    } catch (err) {
      setError(err.message);
    } finally {
      setUpdatingUserId(null);
    }
  }

  async function updateSubscription(accountId) {
    const form = subscriptionForms[accountId];
    if (!form) return;

    setSavingSubscriptionFor(accountId);
    setError("");
    try {
      await apiRequest(`/accounts/${accountId}/subscription`, {
        method: "PUT",
        body: JSON.stringify(form)
      });
      setMessage(t("settings.updatedSubscription"));
      await loadData();
    } catch (err) {
      setError(err.message);
    } finally {
      setSavingSubscriptionFor(null);
    }
  }

  return (
    <div className="page-stack">
      <section className="hero-banner">
        <div>
          <div className="eyebrow">{t("settings.eyebrow")}</div>
          <h1>{t("settings.title")}</h1>
          <p>{t("settings.subtitle")}</p>
        </div>
      </section>

      {error && <div className="inline-error">{error}</div>}
      {message && <div className="inline-success">{message}</div>}

      {loading ? (
        <div className="loading-center">
          <Spinner />
        </div>
      ) : (
        <div className="page-stack">
          <div className="two-column-layout">
            <Card title={t("settings.currentAccount")} subtitle={t("settings.currentAccountSubtitle")} variant="glass">
              <div className="stack-blocks">
                <div className="surface-row">
                  <span>{t("settings.account")}</span>
                  <strong>{user?.account?.name || "Platform"}</strong>
                </div>
                <div className="surface-row">
                  <span>{t("settings.role")}</span>
                  <strong>{user?.role || "-"}</strong>
                </div>
                <div className="surface-row">
                  <span>{t("settings.plan")}</span>
                  <strong>{currentPlan?.name || t("settings.noActivePlan")}</strong>
                </div>
                <div className="surface-row">
                  <span>{t("settings.pageUsage")}</span>
                  <p>
                    {currentUsage?.pages_used ?? 0} / {currentPlan?.max_pages ?? "-"}
                  </p>
                </div>
                <div className="surface-row">
                  <span>{t("settings.userUsage")}</span>
                  <p>
                    {currentUsage?.users_used ?? 0} / {currentPlan?.max_users ?? "-"}
                  </p>
                </div>
                <div className="surface-row">
                  <span>{t("settings.autoIdeaLimit")}</span>
                  <p>
                    {scheduleForm.count} / {currentPlan?.max_auto_ideas_per_day ?? "-"} {t("settings.perRun")}
                  </p>
                </div>
              </div>
            </Card>

            <Card title={t("settings.autoIdeaSchedule")} subtitle={t("settings.autoIdeaScheduleSubtitle")} variant="glass">
              <form className="stack-form" onSubmit={saveSchedule}>
                <label className="toggle-field">
                  <span>{t("settings.enableDailyAuto")}</span>
                  <input
                    type="checkbox"
                    checked={scheduleForm.enabled}
                    onChange={(event) => setScheduleForm({ ...scheduleForm, enabled: event.target.checked })}
                  />
                </label>
                <div className="two-column-grid">
                  <label>
                    {t("settings.runTime")}
                    <input
                      type="time"
                      value={scheduleForm.time_local}
                      onChange={(event) => setScheduleForm({ ...scheduleForm, time_local: event.target.value })}
                    />
                  </label>
                  <label>
                    {t("settings.ideasPerRun")}
                    <select value={String(scheduleForm.count)} onChange={(event) => setScheduleForm({ ...scheduleForm, count: Number(event.target.value) })}>
                      {[1, 3, 5, 7, 10].map((count) => (
                        <option key={count} value={count}>
                          {count} {t("settings.ideas")}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
                <div className="surface-panel schedule-summary">
                  <strong>{t("settings.lastRun")}</strong>
                  <p>{scheduleState.last_run_local_date || t("settings.never")}</p>
                </div>
                <div className="button-row">
                  <button className="primary-button" type="submit" disabled={savingSchedule}>
                    {savingSchedule ? t("settings.saving") : t("settings.saveSchedule")}
                  </button>
                  <button className="secondary-button" type="button" onClick={runScheduleNow} disabled={runningSchedule}>
                    {runningSchedule ? t("settings.queueing") : t("settings.runNow")}
                  </button>
                </div>
              </form>
            </Card>
          </div>

          {canManageSettings && (
            <div className="two-column-layout">
              <Card title={t("settings.accountSettings")} subtitle={t("settings.accountSettingsSubtitle")} variant="glass">
                <form className="stack-form" onSubmit={saveSetting}>
                  <label>
                    {t("settings.key")}
                    <select value={settingForm.key} onChange={(event) => setSettingForm({ ...settingForm, key: event.target.value })}>
                      {(isPlatformAdmin ? PLATFORM_KEYS : SUBSCRIBER_KEYS).map((item) => (
                        <option key={item.value} value={item.value}>
                          {item.label}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    {t("settings.value")}
                    <textarea rows="4" value={settingForm.value_text} onChange={(event) => setSettingForm({ ...settingForm, value_text: event.target.value })} />
                  </label>
                  <label>
                    {t("settings.description")}
                    <input value={settingForm.description} onChange={(event) => setSettingForm({ ...settingForm, description: event.target.value })} />
                  </label>
                  <button className="primary-button" type="submit" disabled={savingSetting}>
                    {savingSetting ? t("settings.saving") : t("settings.saveSetting")}
                  </button>
                </form>
              </Card>

              <Card title={t("settings.savedConfig")} subtitle={t("settings.savedConfigSubtitle")} variant="glass">
                <div className="stack-blocks">
                  {settings.map((item) => (
                    <div key={item.id} className="surface-row">
                      <div>
                        <strong>{item.key}</strong>
                        <p>{item.description || t("settings.noDescription")}</p>
                      </div>
                      <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                        <span className="status-pill">{item.is_encrypted ? t("settings.encrypted") : t("settings.plainText")}</span>
                        <button
                          type="button"
                          className="secondary-button"
                          style={{ padding: "0.2rem 0.6rem", fontSize: "0.78rem" }}
                          disabled={deletingSettingId === item.id}
                          onClick={() => deleteSetting(item.id)}
                        >
                          {deletingSettingId === item.id ? "..." : t("common.delete")}
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </Card>
            </div>
          )}

          <div className="two-column-layout">
            <Card title={t("settings.facebookPages")} subtitle={t("settings.facebookPagesSubtitle")} variant="glass">
              <form className="stack-form" onSubmit={savePage}>
                {isPlatformAdmin && (
                  <label>
                    {t("settings.account")}
                    <select value={pageForm.account_id} onChange={(event) => setPageForm({ ...pageForm, account_id: event.target.value })}>
                      {accounts.map((account) => (
                        <option key={account.id} value={account.id}>
                          {account.name}
                        </option>
                      ))}
                    </select>
                  </label>
                )}
                <label>
                  {t("settings.pageName")}
                  <input value={pageForm.name} onChange={(event) => setPageForm({ ...pageForm, name: event.target.value })} required />
                </label>
                <label>
                  {t("settings.facebookPageId")}
                  <input value={pageForm.facebook_page_id} onChange={(event) => setPageForm({ ...pageForm, facebook_page_id: event.target.value })} required />
                </label>
                <label>
                  {t("settings.category")}
                  <input value={pageForm.page_category} onChange={(event) => setPageForm({ ...pageForm, page_category: event.target.value })} />
                </label>
                <label>
                  {t("settings.descriptionLabel")} <span style={{ color: "var(--text-muted)", fontWeight: 400 }}>{t("settings.descriptionHint")}</span>
                  <textarea rows="3" value={pageForm.description} onChange={(event) => setPageForm({ ...pageForm, description: event.target.value })} placeholder={t("settings.descriptionPlaceholder")} />
                </label>
                <label>
                  {t("settings.accessToken")}
                  <textarea rows="4" value={pageForm.access_token} onChange={(event) => setPageForm({ ...pageForm, access_token: event.target.value })} />
                </label>
                <button className="primary-button" type="submit" disabled={savingPage}>
                  {savingPage ? t("settings.saving") : t("settings.addPage")}
                </button>
              </form>
            </Card>

            <Card title={t("settings.connectedPages")} subtitle={t("settings.connectedPagesSubtitle")} variant="glass">
              <div className="stack-blocks">
                {pages.map((page) => (
                  <div key={page.id} className="surface-panel" style={{ padding: "0.9rem" }}>
                    <div className="surface-row" style={{ paddingTop: 0 }}>
                      <div>
                        <strong>{page.name}</strong>
                        <p className="muted-label">ID: {page.facebook_page_id}{page.page_category ? ` · ${page.page_category}` : ""}</p>
                        {isPlatformAdmin && <p className="muted-label">Account: {accountMap.get(page.account_id)?.name || page.account_id}</p>}
                      </div>
                      <span className="status-pill">{page.is_active ? t("settings.active") : t("settings.disabled")}</span>
                    </div>
                    {page.description && (
                      <p style={{ fontSize: "0.85rem", color: "var(--text-muted)", marginTop: "0.4rem" }}>{page.description}</p>
                    )}
                  </div>
                ))}
              </div>
            </Card>
          </div>

          {canManageAccountUsers && (
            <div className="two-column-layout">
              <Card title={t("settings.userManagement")} subtitle={t("settings.userManagementSubtitle")} variant="glass">
                <form className="stack-form" onSubmit={createUser}>
                  {isPlatformAdmin && (
                    <label>
                      {t("settings.account")}
                      <select value={userForm.account_id} onChange={(event) => setUserForm({ ...userForm, account_id: event.target.value })}>
                        {accounts.map((account) => (
                          <option key={account.id} value={account.id}>
                            {account.name}
                          </option>
                        ))}
                      </select>
                    </label>
                  )}
                  <label>
                    {t("settings.fullName")}
                    <input value={userForm.full_name} onChange={(event) => setUserForm({ ...userForm, full_name: event.target.value })} required />
                  </label>
                  <label>
                    {t("settings.email")}
                    <input type="email" value={userForm.email} onChange={(event) => setUserForm({ ...userForm, email: event.target.value })} required />
                  </label>
                  <label>
                    {t("settings.password")}
                    <input type="password" value={userForm.password} onChange={(event) => setUserForm({ ...userForm, password: event.target.value })} required />
                  </label>
                  <label>
                    {t("settings.roleLabel")}
                    <select value={userForm.role} onChange={(event) => setUserForm({ ...userForm, role: event.target.value })}>
                      {isPlatformAdmin && <option value="platform_admin">Platform Admin</option>}
                      <option value="subscriber_admin">Subscriber Admin</option>
                      <option value="editor">Editor</option>
                    </select>
                  </label>
                  <button className="primary-button" type="submit" disabled={savingUser}>
                    {savingUser ? t("settings.saving") : t("settings.createUser")}
                  </button>
                </form>
              </Card>

              <Card title={t("settings.users")} subtitle={t("settings.usersSubtitle")} variant="glass">
                <div className="stack-blocks">
                  {users.map((item) => (
                    <div key={item.id} className="surface-panel" style={{ padding: "0.75rem" }}>
                      <div className="surface-row" style={{ paddingTop: 0 }}>
                        <div>
                          <strong>{item.full_name}</strong>
                          <p>{item.email}</p>
                          {isPlatformAdmin && <p>Account: {accountMap.get(item.account_id)?.name || "Platform"}</p>}
                        </div>
                        <span className="status-pill" style={{
                          background: !item.is_active ? "var(--danger, #c0392b)" : !item.is_email_verified ? "var(--warning, #e67e22)" : undefined,
                          color: (!item.is_active || !item.is_email_verified) ? "#fff" : undefined
                        }}>
                          {!item.is_active ? t("settings.inactive") : !item.is_email_verified ? t("settings.unverified") : item.role}
                        </span>
                      </div>
                      <div className="button-row" style={{ marginTop: "0.5rem" }}>
                        <select
                          value={item.role}
                          disabled={updatingUserId === item.id}
                          onChange={(event) => updateUser(item.id, { role: event.target.value })}
                          style={{ flex: 1 }}
                        >
                          {isPlatformAdmin && <option value="platform_admin">Platform Admin</option>}
                          <option value="subscriber_admin">Subscriber Admin</option>
                          <option value="editor">Editor</option>
                        </select>
                        {!item.is_email_verified && (
                          <button
                            type="button"
                            className="secondary-button"
                            disabled={updatingUserId === item.id}
                            onClick={() => verifyUser(item.id)}
                          >
                            {t("settings.verify")}
                          </button>
                        )}
                        <button
                          type="button"
                          className="secondary-button"
                          disabled={updatingUserId === item.id}
                          onClick={() => updateUser(item.id, { is_active: !item.is_active })}
                        >
                          {item.is_active ? t("settings.deactivate") : t("settings.activate")}
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </Card>
            </div>
          )}

          {isPlatformAdmin && (
            <>
            <div className="two-column-layout">
              <Card title={t("settings.accounts")} subtitle={t("settings.accountsSubtitle")} variant="glass">
                <form className="stack-form" onSubmit={createAccount}>
                  <label>
                    {t("settings.accountName")}
                    <input
                      value={accountForm.name}
                      onChange={(event) =>
                        setAccountForm({
                          ...accountForm,
                          name: event.target.value,
                          slug: slugify(event.target.value)
                        })
                      }
                      required
                    />
                  </label>
                  <label>
                    {t("settings.slug")}
                    <input value={accountForm.slug} onChange={(event) => setAccountForm({ ...accountForm, slug: slugify(event.target.value) })} required />
                  </label>
                  <label>
                    {t("settings.plan")}
                    <select value={accountForm.plan_code} onChange={(event) => setAccountForm({ ...accountForm, plan_code: event.target.value })}>
                      {plans.map((plan) => (
                        <option key={plan.code} value={plan.code}>
                          {plan.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <button className="primary-button" type="submit" disabled={savingAccount}>
                    {savingAccount ? t("settings.saving") : t("settings.createAccount")}
                  </button>
                </form>
              </Card>

              <Card title={t("settings.plansSubscriptions")} subtitle={t("settings.plansSubscriptionsSubtitle")} variant="glass">
                <div className="stack-blocks">
                  {accounts.map((account) => {
                    const form = subscriptionForms[account.id] || {};
                    return (
                      <div key={account.id} className="surface-panel">
                        <div className="surface-row" style={{ paddingTop: 0 }}>
                          <div>
                            <strong>{account.name}</strong>
                            <p>Slug: {account.slug}</p>
                            <p>
                              {t("settings.usage")}: {account.usage?.pages_used ?? 0}/{account.active_subscription?.plan?.max_pages ?? "-"} pages ·{" "}
                              {account.usage?.users_used ?? 0}/{account.active_subscription?.plan?.max_users ?? "-"} users
                            </p>
                          </div>
                          <span className="status-pill">{account.active_subscription?.plan?.name || t("settings.noPlan")}</span>
                        </div>
                        <div className="two-column-grid" style={{ marginTop: "0.8rem" }}>
                          <label>
                            {t("settings.plan")}
                            <select
                              value={form.plan_code || ""}
                              onChange={(event) =>
                                setSubscriptionForms((current) => ({
                                  ...current,
                                  [account.id]: { ...current[account.id], plan_code: event.target.value }
                                }))
                              }
                            >
                              {plans.map((plan) => (
                                <option key={plan.code} value={plan.code}>
                                  {plan.name} · {plan.max_pages} pages / {plan.max_users} users
                                </option>
                              ))}
                            </select>
                          </label>
                          <label>
                            Status
                            <select
                              value={form.status || "active"}
                              onChange={(event) =>
                                setSubscriptionForms((current) => ({
                                  ...current,
                                  [account.id]: { ...current[account.id], status: event.target.value }
                                }))
                              }
                            >
                              <option value="active">active</option>
                              <option value="past_due">past_due</option>
                              <option value="canceled">canceled</option>
                            </select>
                          </label>
                        </div>
                        <div className="button-row" style={{ marginTop: "0.8rem" }}>
                          <button
                            className="primary-button"
                            type="button"
                            disabled={savingSubscriptionFor === account.id}
                            onClick={() => updateSubscription(account.id)}
                          >
                            {savingSubscriptionFor === account.id ? t("settings.saving") : t("settings.updatePlan")}
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </Card>
            </div>

            {paymentRequests.length > 0 && (
              <Card title={t("settings.paymentRequests")} subtitle={t("settings.paymentRequestsSubtitle")} variant="glass">
                <div className="stack-blocks">
                  {paymentRequests.map((req) => (
                    <div key={req.id} className="surface-panel">
                      <div className="surface-row" style={{ paddingTop: 0 }}>
                        <div>
                          <strong>{req.account_name || `Account #${req.account_id}`}</strong>
                          <p>
                            {t("settings.planLabel")} <strong>{req.plan_code}</strong> · ฿{req.amount?.toLocaleString()}
                          </p>
                          <p>
                            {t("settings.paymentMethod")} {req.payment_method === "promptpay" ? t("settings.promptPay") : t("settings.bankTransfer")}
                            {req.bank_name ? ` (${req.bank_name})` : ""}
                          </p>
                          {req.reference_number && <p>{t("settings.ref")} {req.reference_number}</p>}
                          {req.transfer_date && <p>{t("settings.transferDate")} {req.transfer_date}</p>}
                          {req.note && <p>{t("settings.note")} {req.note}</p>}
                          <p style={{ color: "var(--text-muted)", fontSize: "0.8rem" }}>
                            {new Date(req.created_at).toLocaleDateString("th-TH")}
                          </p>
                          {req.reject_reason && (
                            <p style={{ color: "#c0392b" }}>{t("settings.rejectReason")} {req.reject_reason}</p>
                          )}
                        </div>
                        <span
                          className="status-pill"
                          style={{
                            background:
                              req.status === "approved" ? "#27ae60"
                              : req.status === "rejected" ? "#c0392b"
                              : "#e67e22",
                            color: "#fff",
                          }}
                        >
                          {req.status === "approved" ? t("settings.approvedStatus") : req.status === "rejected" ? t("settings.rejectedStatus") : t("settings.pendingStatus")}
                        </span>
                      </div>

                      {req.status === "pending" && (
                        <div style={{ marginTop: "0.75rem", display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                          <div className="button-row">
                            <button
                              className="primary-button"
                              type="button"
                              disabled={processingRequestId === req.id}
                              onClick={() => approvePayment(req.id)}
                            >
                              {processingRequestId === req.id ? t("settings.processing") : t("settings.approvePayment")}
                            </button>
                          </div>
                          <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                            <input
                              placeholder={t("settings.rejectPlaceholder")}
                              value={rejectForms[req.id] || ""}
                              onChange={(event) =>
                                setRejectForms((prev) => ({ ...prev, [req.id]: event.target.value }))
                              }
                              style={{ flex: 1 }}
                            />
                            <button
                              className="secondary-button"
                              type="button"
                              disabled={processingRequestId === req.id}
                              onClick={() => rejectPayment(req.id)}
                            >
                              {t("settings.rejectButton")}
                            </button>
                          </div>
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
      )}
    </div>
  );
}
