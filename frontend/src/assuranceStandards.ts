// Mirrors backend/app/data_dictionary.py ASSURANCE_STANDARDS - reference text
// only (not governance data), so a small duplicated constant is simpler than
// a dedicated endpoint.
export const ASSURANCE_STANDARDS: Record<
  string,
  { label: string; standard: string; description: string }
> = {
  compilation: {
    label: "Compilation (Notice to Reader)",
    standard: "CSRS 4200",
    description:
      "No assurance is provided - the accountant compiles figures from information the client " +
      "provides without verifying it. CSRS 4200 (2021) replaced the older Section 9200 " +
      "specifically to improve how useful compiled statements are for third-party users like " +
      "lenders. This is the cheapest and most common tier for small businesses.",
  },
  review: {
    label: "Review Engagement",
    standard: "CSRE 2400",
    description:
      "Limited assurance - the accountant performs analytical procedures and inquiry, more " +
      "than a compilation but well short of an audit.",
  },
  audit: {
    label: "Audit",
    standard: "CAS (Canadian Auditing Standards)",
    description:
      "Full (reasonable) assurance - the highest level of verification. Lenders typically " +
      "require reviewed statements for credit facilities up to roughly $5-10M, and audited " +
      "statements above that.",
  },
  none: {
    label: "No assurance engagement (unaudited)",
    standard: "n/a",
    description:
      "The statements are labelled unaudited/management-prepared with no accountant's " +
      "compilation, review, or audit report attached - common for internal or interim " +
      "statements. Treat with the same caution as a compilation, or more.",
  },
  unknown: {
    label: "Could not be determined",
    standard: "n/a",
    description: "No accountant's report or assurance disclaimer was found in the document to classify.",
  },
};
