import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import Card from "../components/Card";
import Spinner from "../components/Spinner";
import { useAuth } from "../context/AuthContext";
import { apiRequest } from "../services/api";
import { isPlatformOwner, roleLabel } from "../utils/roles";

const TONE_OPTIONS = ["Professional", "Friendly", "Luxury", "Casual", "Educational", "Promotional"];
const DEFAULT_ACCOUNT_SETTINGS = {
  default_tone: "Professional",
  content_pillars: ["Education", "Promotion", "Behind the scenes"],
};
const EMPTY_PLATFORM_SETTINGS = {
  openai_api_key: "",
  has_openai_api_key: false,
  default_tone: "Professional",
  content_pillars: ["Education", "Promotion", "Behind the scenes"],
};

function normalizePillars(values) {
  return (Array.isArray(values) ? values : DEFAULT_ACCOUNT_SETTINGS.content_pillars)
    .map((item) => String(item || "").trim())
    .filter(Boolean);
}

function ProgressMeter({ label, used, max }) {
  const limit = Number(max) || 0;
  const current = Number(used) || 0;
  const percent = limit > 0 ? Math.min(100, Math.round((current / limit) * 100)) : 0;
  const nearLimit = limit > 0 && percent >= 80;
  const overLimit = limit > 0 && current >= limit;

  return (
    <div className="usage-meter">
      <div className="surface-row" style={{ padding: 0 }}>
        <strong>{label}</strong>
        <span className={overLimit ? "usage-danger" : nearLimit ? "usage-warning" : ""}>
          {current} / {limit || "-"}
        </span>
      </div>
      <div className="usage-track" aria-hidden="true">
        <span
          className={overLimit ? "danger" : nearLimit ? "warning" : ""}
          style={{ width: `${percent}%` }}
        />
      </div>
      {nearLimit && <p className="muted-label">{overLimit ? "Limit reached." : "Approaching plan limit."}</p>}
    </div>
  );
}

function PillarEditor({ values, onChange, disabled }) {
  const [draft, setDraft] = useState("");

  function addPillar() {
    const next = draft.trim();
    if (!next) return;
    onChange([...values, next]);
    setDraft("");
  }

  function move(index, direction) {
    const next = [...values];
    const target = index + direction;
    if (target < 0 || target >= next.length) return;
    [next[index], next[target]] = [next[target], next[index]];
    onChange(next);
  }

  return (
    <div className="pillar-editor">
      <div className="tag-list">
        {values.map((pillar, index) => (
          <span className="tag-chip" key={`${pillar}-${index}`}>
            {pillar}
            <button type="button" disabled={disabled || index === 0} onClick={() => move(index, -1)} title="Move up">Up</button>
            <button type="button" disabled={disabled || index === values.length - 1} onClick={() => move(index, 1)} title="Move down">Dn</button>
            <button type="button" disabled={disabled} onClick={() => onChange(values.filter((_, itemIndex) => itemIndex !== index))} title="Remove">x</button>
          </span>
        ))}
      </div>
      <div className="button-row">
        <input
          value={draft}
          disabled={disabled}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              addPillar();
            }
          }}
          placeholder="Add content pillar"
        />
        <button className="secondary-button" type="button" disabled={disabled || !draft.trim()} onClick={addPillar}>
          Add
        </button>
      </div>
      <p className="muted-label">Content pillars define the main themes used by AI when generating ideas.</p>
    </div>
  );
}

function sameSettings(left, right) {
  return JSON.stringify(left) === JSON.stringify(right);
}

function pagePreferenceValues(page, accountSettings) {
  return {
    default_tone: page.default_tone || accountSettings.default_tone,
    content_pillars: normalizePillars(page.content_pillars?.length ? page.content_pillars : accountSettings.content_pillars),
  };
}

export default function SettingsPage() {
  const { user, hasSubscription } = useAuth();
  const isPlatformAdmin = isPlatformOwner(user);
  const canEditAccountSettings = user?.role === "subscriber_admin";
  const canManagePages = user?.role === "subscriber_admin" && hasSubscription;
  const canEditPagePreferences = (user?.role === "subscriber_admin" || user?.role === "editor") && hasSubscription;
  const canManageUsers = user?.role === "subscriber_admin" && hasSubscription;

  const [loading, setLoading] = useState(true);
  const [usageLoading, setUsageLoading] = useState(true);
  const [usageError, setUsageError] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [usage, setUsage] = useState(null);
  const [accounts, setAccounts] = useState([]);
  const [accountSettings, setAccountSettings] = useState(DEFAULT_ACCOUNT_SETTINGS);
  const [savedAccountSettings, setSavedAccountSettings] = useState(DEFAULT_ACCOUNT_SETTINGS);
  const [platformSettings, setPlatformSettings] = useState(EMPTY_PLATFORM_SETTINGS);
  const [savedPlatformSettings, setSavedPlatformSettings] = useState(EMPTY_PLATFORM_SETTINGS);
  const [apiKeyDraft, setApiKeyDraft] = useState("");
  const [savingAccount, setSavingAccount] = useState(false);
  const [savingPlatform, setSavingPlatform] = useState(false);
  const [savingApiKey, setSavingApiKey] = useState(false);
  const [pages, setPages] = useState([]);
  const [pageForm, setPageForm] = useState({
    name: "",
    facebook_page_id: "",
    page_category: "",
    description: "",
    access_token: "",
    default_tone: DEFAULT_ACCOUNT_SETTINGS.default_tone,
    content_pillars: DEFAULT_ACCOUNT_SETTINGS.content_pillars,
    is_active: true,
  });
  const [savingPage, setSavingPage] = useState(false);
  const [savingPagePreferencesId, setSavingPagePreferencesId] = useState(null);
  const [deletingPageId, setDeletingPageId] = useState(null);
  const [users, setUsers] = useState([]);
  const [userForm, setUserForm] = useState({
    email: "",
    full_name: "",
    password: "",
    role: "editor",
    assigned_page_ids: [],
  });
  const [savingUser, setSavingUser] = useState(false);
  const [updatingUserId, setUpdatingUserId] = useState(null);

  const accountDirty = useMemo(
    () => !sameSettings(accountSettings, savedAccountSettings),
    [accountSettings, savedAccountSettings]
  );
  const platformDirty = useMemo(
    () =>
      !sameSettings(
        {
          default_tone: platformSettings.default_tone,
          content_pillars: platformSettings.content_pillars,
        },
        {
          default_tone: savedPlatformSettings.default_tone,
          content_pillars: savedPlatformSettings.content_pillars,
        }
      ),
    [platformSettings, savedPlatformSettings]
  );

  async function loadSettings() {
    setLoading(true);
    setUsageLoading(true);
    setError("");
    setUsageError("");
    try {
      const [settingsData, usageData, pagesData, usersData, accountsData] = await Promise.all([
        apiRequest("/settings"),
        isPlatformAdmin ? Promise.resolve(null) : apiRequest("/settings/usage").catch((err) => {
          setUsageError(err.message);
          return null;
        }),
        (canEditPagePreferences || canManageUsers) ? apiRequest("/pages").catch(() => []) : Promise.resolve([]),
        canManageUsers ? apiRequest("/users").catch(() => []) : Promise.resolve([]),
        isPlatformAdmin ? apiRequest("/accounts").catch(() => []) : Promise.resolve([]),
      ]);
      const nextAccount = {
        default_tone: settingsData.account?.default_tone || DEFAULT_ACCOUNT_SETTINGS.default_tone,
        content_pillars: normalizePillars(settingsData.account?.content_pillars),
      };
      const nextPlatform = {
        ...EMPTY_PLATFORM_SETTINGS,
        ...(settingsData.platform || {}),
        content_pillars: normalizePillars(settingsData.platform?.content_pillars),
      };
      setAccountSettings(nextAccount);
      setSavedAccountSettings(nextAccount);
      setPlatformSettings(nextPlatform);
      setSavedPlatformSettings(nextPlatform);
      setUsage(usageData);
      setPages(pagesData || []);
      setUsers(usersData || []);
      setAccounts(accountsData || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
      setUsageLoading(false);
    }
  }

  useEffect(() => {
    loadSettings();
  }, []);

  useEffect(() => {
    if (!message) return undefined;
    const timer = setTimeout(() => setMessage(""), 4000);
    return () => clearTimeout(timer);
  }, [message]);

  useEffect(() => {
    setPageForm((current) => {
      if (current.name || current.facebook_page_id) return current;
      return {
        ...current,
        default_tone: accountSettings.default_tone,
        content_pillars: accountSettings.content_pillars,
      };
    });
  }, [accountSettings.default_tone, accountSettings.content_pillars]);

  async function saveAccountSettings(event) {
    event.preventDefault();
    if (accountSettings.content_pillars.length === 0) {
      setError("Content pillars cannot be empty.");
      return;
    }
    setSavingAccount(true);
    setError("");
    try {
      await apiRequest("/settings?scope=account", {
        method: "PATCH",
        body: JSON.stringify(accountSettings),
      });
      setSavedAccountSettings(accountSettings);
      setMessage("Account preferences saved.");
    } catch (err) {
      setError(err.message);
    } finally {
      setSavingAccount(false);
    }
  }

  async function savePlatformSettings(event) {
    event.preventDefault();
    if (platformSettings.content_pillars.length === 0) {
      setError("Platform content pillars cannot be empty.");
      return;
    }
    setSavingPlatform(true);
    setError("");
    try {
      await apiRequest("/settings?scope=platform", {
        method: "PATCH",
        body: JSON.stringify({
          default_tone: platformSettings.default_tone,
          content_pillars: platformSettings.content_pillars,
        }),
      });
      setSavedPlatformSettings(platformSettings);
      setMessage("Platform settings saved.");
    } catch (err) {
      setError(err.message);
    } finally {
      setSavingPlatform(false);
    }
  }

  async function saveApiKey(event) {
    event.preventDefault();
    if (!apiKeyDraft.trim()) {
      setError("Enter a new API key before saving.");
      return;
    }
    setSavingApiKey(true);
    setError("");
    try {
      await apiRequest("/settings?scope=platform", {
        method: "PATCH",
        body: JSON.stringify({ openai_api_key: apiKeyDraft }),
      });
      setApiKeyDraft("");
      setPlatformSettings((current) => ({ ...current, openai_api_key: "********", has_openai_api_key: true }));
      setSavedPlatformSettings((current) => ({ ...current, openai_api_key: "********", has_openai_api_key: true }));
      setMessage("OpenAI API key updated.");
    } catch (err) {
      setError(err.message);
    } finally {
      setSavingApiKey(false);
    }
  }

  async function createPage(event) {
    event.preventDefault();
    if (normalizePillars(pageForm.content_pillars).length === 0) {
      setError("Page content pillars cannot be empty.");
      return;
    }
    setSavingPage(true);
    setError("");
    try {
      await apiRequest("/pages", {
        method: "POST",
        body: JSON.stringify({
          name: pageForm.name,
          facebook_page_id: pageForm.facebook_page_id,
          page_category: pageForm.page_category || null,
          description: pageForm.description || null,
          access_token: pageForm.access_token || null,
          default_tone: pageForm.default_tone || accountSettings.default_tone,
          content_pillars: normalizePillars(pageForm.content_pillars),
          is_active: pageForm.is_active,
        }),
      });
      setPageForm({
        name: "",
        facebook_page_id: "",
        page_category: "",
        description: "",
        access_token: "",
        default_tone: accountSettings.default_tone,
        content_pillars: accountSettings.content_pillars,
        is_active: true,
      });
      setMessage("Page created.");
      await loadSettings();
    } catch (err) {
      setError(err.message);
    } finally {
      setSavingPage(false);
    }
  }

  function updatePageLocal(pageId, patch) {
    setPages((current) => current.map((page) => (page.id === pageId ? { ...page, ...patch } : page)));
  }

  async function deletePage(pageId, pageName) {
    if (!window.confirm(`Delete page "${pageName}"? This cannot be undone.`)) return;
    setDeletingPageId(pageId);
    setError("");
    try {
      await apiRequest(`/pages/${pageId}`, { method: "DELETE" });
      setPages((current) => current.filter((p) => p.id !== pageId));
      setMessage(`Page "${pageName}" deleted.`);
    } catch (err) {
      setError(err.message);
    } finally {
      setDeletingPageId(null);
    }
  }

  async function savePagePreferences(page) {
    const preferences = pagePreferenceValues(page, accountSettings);
    if (preferences.content_pillars.length === 0) {
      setError("Page content pillars cannot be empty.");
      return;
    }
    setSavingPagePreferencesId(page.id);
    setError("");
    try {
      const updated = await apiRequest(`/pages/${page.id}/preferences`, {
        method: "PATCH",
        body: JSON.stringify(preferences),
      });
      updatePageLocal(page.id, updated);
      setMessage(`Page preferences saved for ${page.name}.`);
    } catch (err) {
      setError(err.message);
    } finally {
      setSavingPagePreferencesId(null);
    }
  }

  function toggleAssignedPage(pageId) {
    setUserForm((current) => {
      const currentIds = current.assigned_page_ids || [];
      const nextIds = currentIds.includes(pageId)
        ? currentIds.filter((id) => id !== pageId)
        : [...currentIds, pageId];
      return { ...current, assigned_page_ids: nextIds };
    });
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
          role: isPlatformAdmin ? userForm.role : "editor",
          assigned_page_ids: userForm.role === "editor" ? userForm.assigned_page_ids : [],
        }),
      });
      setUserForm({ email: "", full_name: "", password: "", role: "editor", assigned_page_ids: [] });
      setMessage("User created.");
      await loadSettings();
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
      await apiRequest(`/users/${userId}`, {
        method: "PUT",
        body: JSON.stringify(patch),
      });
      setMessage("User updated.");
      await loadSettings();
    } catch (err) {
      setError(err.message);
    } finally {
      setUpdatingUserId(null);
    }
  }

  return (
    <div className="page-stack">
      <section className="page-header">
        <div>
          <h1>Settings</h1>
          <p>Manage your account preferences, content style, and usage limits.</p>
        </div>
      </section>

      {error && <div className="inline-error">{error}</div>}
      {message && <div className="inline-success">{message}</div>}

      {loading ? (
        <div className="loading-center">
          <Spinner />
        </div>
      ) : (
        <>
          {isPlatformAdmin && (
            <Card title="Subscriber Accounts" subtitle="Manage customer accounts and shared subscription credit from Platform View." variant="glass">
              {accounts.length === 0 ? (
                <div className="empty-state centered">
                  <p>No subscriber accounts yet.</p>
                </div>
              ) : (
                <div className="table-shell">
                  <table>
                    <thead>
                      <tr>
                        <th>Account</th>
                        <th>Plan</th>
                        <th>Credit Status</th>
                        <th>Usage</th>
                      </tr>
                    </thead>
                    <tbody>
                      {accounts.map((account) => {
                        const subscription = account.active_subscription;
                        const plan = subscription?.plan;
                        return (
                          <tr key={account.id}>
                            <td>
                              <strong>{account.name}</strong>
                              <p className="muted-label">{account.slug}</p>
                            </td>
                            <td>{plan ? `${plan.name} / ฿${plan.price_monthly.toLocaleString()}` : "No plan"}</td>
                            <td>
                              <span className="status-pill">{subscription?.status || "no credit"}</span>
                            </td>
                            <td>
                              {account.usage?.pages_used ?? 0}/{plan?.max_pages ?? "-"} pages ·{" "}
                              {account.usage?.users_used ?? 0}/{plan?.max_users ?? "-"} users
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </Card>
          )}

          {!isPlatformAdmin && (
            <Card title="Usage Overview" variant="glass">
              {usageLoading ? (
                <div className="loading-center"><Spinner /></div>
              ) : usageError ? (
                <div className="inline-error">{usageError}</div>
              ) : (
                <div className="usage-overview">
                  {!hasSubscription && (
                    <div className="subscription-warning">
                      <div>
                        <strong>Your account does not have an active subscription.</strong>
                        <p>Please submit a payment request from Billing.</p>
                      </div>
                      <Link className="primary-button" to="/billing">Go to Billing</Link>
                    </div>
                  )}
                  <div className="usage-grid">
                    <ProgressMeter label="Pages" used={usage?.pages_used} max={usage?.max_pages} />
                    <ProgressMeter label="Users" used={usage?.users_used} max={usage?.max_users} />
                    <ProgressMeter label="Auto Ideas Today" used={usage?.auto_ideas_used_today} max={usage?.max_auto_ideas_per_day} />
                  </div>
                </div>
              )}
            </Card>
          )}

          {!isPlatformAdmin && (
            <Card title="Content Preferences" variant="glass">
              <form className="stack-form" onSubmit={saveAccountSettings}>
                <label>
                  Default Tone
                  <select
                    disabled={!canEditAccountSettings}
                    value={accountSettings.default_tone}
                    onChange={(event) => setAccountSettings({ ...accountSettings, default_tone: event.target.value })}
                  >
                    {TONE_OPTIONS.map((tone) => (
                      <option key={tone} value={tone}>{tone}</option>
                    ))}
                  </select>
                </label>
                <label>
                  Content Pillars
                  <PillarEditor
                    disabled={!canEditAccountSettings}
                    values={accountSettings.content_pillars}
                    onChange={(content_pillars) => setAccountSettings({ ...accountSettings, content_pillars })}
                  />
                </label>
                {canEditAccountSettings ? (
                  <button className="primary-button" type="submit" disabled={savingAccount || !accountDirty}>
                    {savingAccount ? "Saving..." : "Save Content Preferences"}
                  </button>
                ) : null}
              </form>
            </Card>
          )}

          {canEditPagePreferences && (
            <Card
              title={canManagePages ? "Pages" : "Assigned Page Preferences"}
              subtitle={
                canManagePages
                  ? "Create Facebook pages within the page limit included in your package, then tune each page's content preferences."
                  : "Tune content preferences for the pages assigned to you."
              }
              variant="glass"
            >
              <div className="two-column-layout">
                {canManagePages && (
                  <form className="stack-form" onSubmit={createPage}>
                    <div className="surface-panel" style={{ padding: "0.85rem" }}>
                      <div className="surface-row" style={{ padding: 0 }}>
                        <span>Package Limit</span>
                        <strong>{usage?.pages_used ?? pages.length} / {usage?.max_pages || "-"}</strong>
                      </div>
                    </div>
                    <label>
                      Page Name
                      <input
                        value={pageForm.name}
                        onChange={(event) => setPageForm({ ...pageForm, name: event.target.value })}
                        required
                      />
                    </label>
                    <label>
                      Facebook Page ID
                      <input
                        value={pageForm.facebook_page_id}
                        onChange={(event) => setPageForm({ ...pageForm, facebook_page_id: event.target.value })}
                        required
                      />
                    </label>
                    <label>
                      Category
                      <input
                        value={pageForm.page_category}
                        onChange={(event) => setPageForm({ ...pageForm, page_category: event.target.value })}
                        placeholder="Education, Retail, Health..."
                      />
                    </label>
                    <label>
                      Description
                      <textarea
                        rows="3"
                        value={pageForm.description}
                        onChange={(event) => setPageForm({ ...pageForm, description: event.target.value })}
                      />
                    </label>
                    <label>
                      Default Tone
                      <select
                        value={pageForm.default_tone}
                        onChange={(event) => setPageForm({ ...pageForm, default_tone: event.target.value })}
                      >
                        {TONE_OPTIONS.map((tone) => (
                          <option key={tone} value={tone}>{tone}</option>
                        ))}
                      </select>
                    </label>
                    <label>
                      Content Pillars
                      <PillarEditor
                        values={normalizePillars(pageForm.content_pillars)}
                        onChange={(content_pillars) => setPageForm({ ...pageForm, content_pillars })}
                      />
                    </label>
                    <label>
                      Access Token
                      <textarea
                        rows="3"
                        value={pageForm.access_token}
                        onChange={(event) => setPageForm({ ...pageForm, access_token: event.target.value })}
                        placeholder="Saved encrypted. Leave empty if you will add it later."
                      />
                    </label>
                    <label className="toggle-field">
                      <span>Active</span>
                      <input
                        type="checkbox"
                        checked={pageForm.is_active}
                        onChange={(event) => setPageForm({ ...pageForm, is_active: event.target.checked })}
                      />
                    </label>
                    <button
                      className="primary-button"
                      type="submit"
                      disabled={savingPage || (!isPlatformAdmin && usage?.max_pages && (usage?.pages_used ?? pages.length) >= usage.max_pages)}
                      title={!isPlatformAdmin && usage?.max_pages && (usage?.pages_used ?? pages.length) >= usage.max_pages ? "Page limit reached for this package." : undefined}
                    >
                      {savingPage ? "Creating..." : "Create Page"}
                    </button>
                  </form>
                )}

                <div className="stack-blocks">
                  {pages.length === 0 ? (
                    <div className="empty-state centered">
                      <p>No pages yet.</p>
                    </div>
                  ) : (
                    pages.map((page) => {
                      const preferences = pagePreferenceValues(page, accountSettings);
                      return (
                        <div key={page.id} className="surface-panel" style={{ padding: "0.85rem" }}>
                          <div className="surface-row" style={{ paddingTop: 0 }}>
                            <div>
                              <strong>{page.name}</strong>
                              <p className="muted-label">ID: {page.facebook_page_id}</p>
                              {page.page_category && <p className="muted-label">{page.page_category}</p>}
                            </div>
                            <span className="status-pill">{page.is_active ? "Active" : "Inactive"}</span>
                          </div>
                          {page.description && <p>{page.description}</p>}
                          <div className="stack-form" style={{ marginTop: "0.85rem" }}>
                            <label>
                              Default Tone
                              <select
                                value={preferences.default_tone}
                                onChange={(event) => updatePageLocal(page.id, { default_tone: event.target.value })}
                              >
                                {TONE_OPTIONS.map((tone) => (
                                  <option key={tone} value={tone}>{tone}</option>
                                ))}
                              </select>
                            </label>
                            <label>
                              Content Pillars
                              <PillarEditor
                                values={preferences.content_pillars}
                                onChange={(content_pillars) => updatePageLocal(page.id, { content_pillars })}
                              />
                            </label>
                            <div style={{ display: "flex", gap: "0.5rem" }}>
                              <button
                                className="secondary-button"
                                type="button"
                                disabled={savingPagePreferencesId === page.id}
                                onClick={() => savePagePreferences(page)}
                                style={{ flex: 1 }}
                              >
                                {savingPagePreferencesId === page.id ? "Saving..." : "Save Page Preferences"}
                              </button>
                              {canManagePages && (
                                <button
                                  className="danger-button"
                                  type="button"
                                  disabled={deletingPageId === page.id}
                                  onClick={() => deletePage(page.id, page.name)}
                                >
                                  {deletingPageId === page.id ? "Deleting..." : "Delete"}
                                </button>
                              )}
                            </div>
                          </div>
                        </div>
                      );
                    })
                  )}
                </div>
              </div>
            </Card>
          )}

          {canManageUsers && (
            <Card title="Team Access" subtitle="Manage editor users and the pages they can work on." variant="glass">
              <div className="two-column-layout">
                <form className="stack-form" onSubmit={createUser}>
                  <label>
                    Full Name
                    <input
                      value={userForm.full_name}
                      onChange={(event) => setUserForm({ ...userForm, full_name: event.target.value })}
                      required
                    />
                  </label>
                  <label>
                    Email
                    <input
                      type="email"
                      value={userForm.email}
                      onChange={(event) => setUserForm({ ...userForm, email: event.target.value })}
                      required
                    />
                  </label>
                  <label>
                    Password
                    <input
                      type="password"
                      value={userForm.password}
                      onChange={(event) => setUserForm({ ...userForm, password: event.target.value })}
                      required
                    />
                  </label>
                  <label>
                    Role
                    <select
                      value={userForm.role}
                      disabled={!isPlatformAdmin}
                      onChange={(event) => setUserForm({ ...userForm, role: event.target.value, assigned_page_ids: [] })}
                    >
                      {isPlatformAdmin && <option value="platform_owner">Platform Owner</option>}
                      {isPlatformAdmin && <option value="subscriber_admin">Subscriber Admin</option>}
                      <option value="editor">Editor</option>
                    </select>
                  </label>
                  {userForm.role === "editor" && (
                    <div className="stack-form">
                      <strong>Assigned Pages</strong>
                      {pages.length === 0 ? (
                        <p className="muted-label">Create a page before assigning editor access.</p>
                      ) : (
                        <div className="tag-list">
                          {pages.map((page) => (
                            <label key={page.id} className="tag-chip" style={{ cursor: "pointer" }}>
                              <input
                                type="checkbox"
                                checked={userForm.assigned_page_ids.includes(page.id)}
                                onChange={() => toggleAssignedPage(page.id)}
                              />
                              {page.name}
                            </label>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                  <button className="primary-button" type="submit" disabled={savingUser}>
                    {savingUser ? "Creating..." : "Create User"}
                  </button>
                </form>

                <div className="stack-blocks">
                  {users.length === 0 ? (
                    <div className="empty-state centered">
                      <p>No team users yet.</p>
                    </div>
                  ) : (
                    users.map((item) => (
                      <div key={item.id} className="surface-panel" style={{ padding: "0.85rem" }}>
                        <div className="surface-row" style={{ paddingTop: 0 }}>
                          <div>
                            <strong>{item.full_name}</strong>
                            <p>{item.email}</p>
                            <p className="muted-label">{roleLabel(item.role)}</p>
                          </div>
                          <span className="status-pill">{item.is_active ? "Active" : "Inactive"}</span>
                        </div>
                        {item.role === "editor" && (
                          <div className="stack-form" style={{ marginTop: "0.75rem" }}>
                            <strong>Assigned Pages</strong>
                            <div className="tag-list">
                              {pages.map((page) => {
                                const assigned = item.assigned_page_ids?.includes(page.id);
                                return (
                                  <label key={page.id} className="tag-chip" style={{ cursor: "pointer" }}>
                                    <input
                                      type="checkbox"
                                      checked={Boolean(assigned)}
                                      disabled={updatingUserId === item.id}
                                      onChange={() => {
                                        const currentIds = item.assigned_page_ids || [];
                                        const nextIds = assigned
                                          ? currentIds.filter((id) => id !== page.id)
                                          : [...currentIds, page.id];
                                        updateUser(item.id, { assigned_page_ids: nextIds });
                                      }}
                                    />
                                    {page.name}
                                  </label>
                                );
                              })}
                            </div>
                          </div>
                        )}
                        <div className="button-row" style={{ marginTop: "0.75rem" }}>
                          {isPlatformAdmin && (
                            <select
                              value={item.role}
                              disabled={updatingUserId === item.id}
                              onChange={(event) => updateUser(item.id, { role: event.target.value })}
                            >
                              <option value="platform_owner">Platform Owner</option>
                              <option value="subscriber_admin">Subscriber Admin</option>
                              <option value="editor">Editor</option>
                            </select>
                          )}
                          <button
                            className="secondary-button"
                            type="button"
                            disabled={updatingUserId === item.id}
                            onClick={() => updateUser(item.id, { is_active: !item.is_active })}
                          >
                            {item.is_active ? "Deactivate" : "Activate"}
                          </button>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </Card>
          )}

          {isPlatformAdmin && (
            <Card title="Platform Settings" variant="glass">
              <div className="settings-section-stack">
                <form className="stack-form" onSubmit={saveApiKey}>
                  <label>
                    OpenAI API Key
                    <input
                      type="password"
                      value={apiKeyDraft}
                      onChange={(event) => setApiKeyDraft(event.target.value)}
                      placeholder={platformSettings.has_openai_api_key ? "********" : "No key saved"}
                    />
                  </label>
                  <button className="primary-button" type="submit" disabled={savingApiKey || !apiKeyDraft.trim()}>
                    {savingApiKey ? "Updating..." : "Update API Key"}
                  </button>
                </form>

                <form className="stack-form" onSubmit={savePlatformSettings}>
                  <label>
                    Platform Default Tone
                    <select
                      value={platformSettings.default_tone}
                      onChange={(event) => setPlatformSettings({ ...platformSettings, default_tone: event.target.value })}
                    >
                      {TONE_OPTIONS.map((tone) => (
                        <option key={tone} value={tone}>{tone}</option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Platform Content Pillars
                    <PillarEditor
                      values={platformSettings.content_pillars}
                      onChange={(content_pillars) => setPlatformSettings({ ...platformSettings, content_pillars })}
                    />
                  </label>
                  <button className="primary-button" type="submit" disabled={savingPlatform || !platformDirty}>
                    {savingPlatform ? "Saving..." : "Save Platform Defaults"}
                  </button>
                </form>
              </div>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
