import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import Card from "../components/Card";
import Spinner from "../components/Spinner";
import StatusPill from "../components/StatusPill";
import { useLang } from "../context/LangContext";
import { apiRequest } from "../services/api";

const WEEKDAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function toLocalDateKey(value) {
  const date = new Date(value);
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function monthLabel(date) {
  return date.toLocaleDateString("th-TH", {
    year: "numeric",
    month: "long"
  });
}

function buildCalendarDays(activeMonth) {
  const year = activeMonth.getFullYear();
  const month = activeMonth.getMonth();
  const firstDay = new Date(year, month, 1);
  const firstWeekday = (firstDay.getDay() + 6) % 7;
  const gridStart = new Date(year, month, 1 - firstWeekday);
  return Array.from({ length: 42 }, (_, index) => {
    const date = new Date(gridStart);
    date.setDate(gridStart.getDate() + index);
    return date;
  });
}

function formatScheduledDate(value) {
  return new Date(value).toLocaleDateString("th-TH", {
    weekday: "short",
    day: "numeric",
    month: "short"
  });
}

export default function ContentCalendarPage() {
  const { t } = useLang();
  const [calendarItems, setCalendarItems] = useState([]);
  const [posts, setPosts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [activeMonth, setActiveMonth] = useState(() => {
    const today = new Date();
    return new Date(today.getFullYear(), today.getMonth(), 1);
  });

  useEffect(() => {
    Promise.all([apiRequest("/content-calendar"), apiRequest("/posts")])
      .then(([calendarData, postData]) => {
        setCalendarItems(calendarData);
        setPosts(postData);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  const scheduledPosts = useMemo(
    () => posts.filter((post) => post.scheduled_for),
    [posts]
  );

  const scheduledCalendarOnly = useMemo(() => {
    const linkedCalendarIds = new Set(
      scheduledPosts.map((post) => post.calendar_id).filter(Boolean)
    );

    return calendarItems.filter(
      (item) => item.scheduled_date && !linkedCalendarIds.has(item.id)
    );
  }, [calendarItems, scheduledPosts]);

  const scheduledEntries = useMemo(() => {
    const fromPosts = scheduledPosts.map((post) => ({
      id: `post-${post.id}`,
      title: post.title,
      topic: post.caption || post.content_pillar,
      status: post.status,
      dateValue: post.scheduled_for,
      link: `/posts/${post.id}/edit`,
      linkLabel: t("calendar.openPost"),
      source: "post"
    }));

    const fromCalendar = scheduledCalendarOnly.map((item) => ({
      id: `calendar-${item.id}`,
      title: item.title,
      topic: item.topic,
      status: item.status,
      dateValue: item.scheduled_date,
      link: `/studio?calendar_id=${item.id}`,
      linkLabel: t("calendar.openInStudio"),
      source: "calendar"
    }));

    return [...fromPosts, ...fromCalendar];
  }, [scheduledPosts, scheduledCalendarOnly]);

  const unscheduledItems = useMemo(
    () => calendarItems.filter((item) => !item.scheduled_date),
    [calendarItems]
  );

  const itemsByDay = useMemo(() => {
    return scheduledEntries.reduce((accumulator, entry) => {
      const key = toLocalDateKey(entry.dateValue);
      if (!accumulator[key]) accumulator[key] = [];
      accumulator[key].push(entry);
      return accumulator;
    }, {});
  }, [scheduledEntries]);

  const monthDays = useMemo(() => buildCalendarDays(activeMonth), [activeMonth]);
  const activeYear = activeMonth.getFullYear();
  const activeMonthIndex = activeMonth.getMonth();

  const monthEntries = scheduledEntries
    .filter((entry) => {
      const date = new Date(entry.dateValue);
      return date.getFullYear() === activeYear && date.getMonth() === activeMonthIndex;
    })
    .sort((left, right) => new Date(left.dateValue) - new Date(right.dateValue));

  return (
    <div className="page-stack">
      <section className="hero-banner">
        <div>
          <div className="eyebrow">{t("calendar.eyebrow")}</div>
          <h1>{t("calendar.title")}</h1>
          <p>{t("calendar.subtitle")}</p>
        </div>
        <div className="hero-actions">
          <Link className="primary-button" to="/studio">
            {t("calendar.addBrief")}
          </Link>
        </div>
      </section>

      {error && <div className="inline-error">{error}</div>}

      {loading ? (
        <div className="loading-center">
          <Spinner />
        </div>
      ) : calendarItems.length === 0 && posts.length === 0 ? (
        <Card variant="glass">
          <div className="empty-state centered">
            <p>{t("calendar.noData")}</p>
            <Link className="primary-button" to="/studio">
              {t("calendar.createFirstIdea")}
            </Link>
          </div>
        </Card>
      ) : (
        <>
          <Card
            title={monthLabel(activeMonth)}
            subtitle={t("calendar.itemsThisMonth").replace("{count}", monthEntries.length)}
            actions={
              <div className="button-row">
                <button
                  className="ghost-button"
                  type="button"
                  onClick={() => setActiveMonth(new Date(activeYear, activeMonthIndex - 1, 1))}
                >
                  {t("calendar.prevMonth")}
                </button>
                <button className="ghost-button" type="button" onClick={() => setActiveMonth(new Date())}>
                  {t("calendar.thisMonth")}
                </button>
                <button
                  className="ghost-button"
                  type="button"
                  onClick={() => setActiveMonth(new Date(activeYear, activeMonthIndex + 1, 1))}
                >
                  {t("calendar.nextMonth")}
                </button>
              </div>
            }
            variant="glass"
          >
            <div className="month-calendar">
              <div className="month-weekdays">
                {WEEKDAY_LABELS.map((label) => (
                  <div key={label} className="month-weekday">
                    {label}
                  </div>
                ))}
              </div>

              <div className="month-grid">
                {monthDays.map((date) => {
                  const key = toLocalDateKey(date);
                  const entries = itemsByDay[key] || [];
                  const inMonth = date.getMonth() === activeMonthIndex;
                  const isToday = toLocalDateKey(date) === toLocalDateKey(new Date());

                  return (
                    <article
                      key={key}
                      className={`month-cell${inMonth ? "" : " is-outside"}${isToday ? " is-today" : ""}`}
                    >
                      <header className="month-cell-header">
                        <strong>{date.getDate()}</strong>
                        {entries.length > 0 ? <span className="month-cell-count">{entries.length}</span> : null}
                      </header>

                      <div className="month-cell-items">
                        {entries.slice(0, 3).map((entry) => (
                          <Link key={entry.id} to={entry.link} className="month-entry">
                            <StatusPill status={entry.status} />
                            <span>{entry.title}</span>
                          </Link>
                        ))}
                        {entries.length > 3 ? <div className="month-entry more">+{entries.length - 3} more</div> : null}
                      </div>
                    </article>
                  );
                })}
              </div>
            </div>
          </Card>

          <div className="two-column-layout">
            <Card title={t("calendar.scheduledItems")} subtitle={t("calendar.scheduledSubtitle")} variant="glass">
              <div className="stack-blocks">
                {monthEntries.length === 0 ? (
                  <div className="empty-state centered">
                    <p>{t("calendar.noScheduledThisMonth")}</p>
                  </div>
                ) : (
                  monthEntries.map((entry) => (
                    <div key={entry.id} className="surface-panel" style={{ padding: "1rem" }}>
                      <div className="surface-row" style={{ paddingTop: 0 }}>
                        <div>
                          <strong>{entry.title}</strong>
                          <p className="muted-label" style={{ marginTop: "0.25rem" }}>
                            {formatScheduledDate(entry.dateValue)}
                          </p>
                        </div>
                        <StatusPill status={entry.status} />
                      </div>
                      <p>{entry.topic || t("calendar.noTopicExtra")}</p>
                      <div className="button-row" style={{ marginTop: "0.75rem" }}>
                        <Link className="ghost-button" to={entry.link}>
                          {entry.linkLabel}
                        </Link>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </Card>

            <Card title={t("calendar.unscheduledBacklog")} subtitle={t("calendar.unscheduledSubtitle")} variant="glass">
              <div className="stack-blocks">
                {unscheduledItems.length === 0 ? (
                  <div className="empty-state centered">
                    <p>{t("calendar.noBacklog")}</p>
                  </div>
                ) : (
                  unscheduledItems.map((item) => (
                    <div key={item.id} className="surface-panel" style={{ padding: "1rem" }}>
                      <div className="surface-row" style={{ paddingTop: 0 }}>
                        <strong>{item.title}</strong>
                        <StatusPill status={item.status} />
                      </div>
                      <p>{item.topic || t("calendar.noTopicMore")}</p>
                      <div className="button-row" style={{ marginTop: "0.75rem" }}>
                        <Link className="ghost-button" to={`/studio?calendar_id=${item.id}`}>
                          {t("calendar.openInStudio")}
                        </Link>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </Card>
          </div>
        </>
      )}
    </div>
  );
}
