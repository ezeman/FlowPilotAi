import { useLang } from "../context/LangContext";

const COLOR_MAP = {
  idea: "pill-idea",
  generating: "pill-generating",
  draft: "pill-draft",
  ready_for_review: "pill-review",
  approved: "pill-approved",
  scheduled: "pill-scheduled",
  publishing: "pill-publishing",
  posted: "pill-posted",
  failed: "pill-failed",
  success: "pill-success"
};

export default function StatusPill({ status, label }) {
  const { t } = useLang();
  const translatedLabel = label || t(`status.${status}`) || status;
  return (
    <span className={`status-pill ${COLOR_MAP[status] || "pill-draft"}`}>
      {translatedLabel}
    </span>
  );
}
