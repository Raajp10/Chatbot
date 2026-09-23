// Static audience disclaimer text (FR-024) — not sourced from the API. Implemented in T019.

const DISCLAIMER_TEXT =
  "This tool is intended for currently registered PNW undergraduate and graduate students.";

function DisclaimerBanner() {
  return <div className="disclaimer-banner">{DISCLAIMER_TEXT}</div>;
}

export default DisclaimerBanner;
