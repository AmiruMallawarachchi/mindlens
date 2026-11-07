/**
 * The countries MindLens has direct crisis numbers for.
 *
 * This list must match `_COUNTRY_RESOURCES` in
 * backend/app/core/crisis_resources.py — the backend is authoritative and
 * falls back to international directories for anything not listed here, so a
 * stale entry can only ever mean one more option in the picker, never a wrong
 * number on screen.
 */

export interface CrisisCountry {
  code: string;
  label: string;
}

export const CRISIS_COUNTRIES: CrisisCountry[] = [
  { code: "AU", label: "Australia" },
  { code: "CA", label: "Canada" },
  { code: "DE", label: "Germany" },
  { code: "FR", label: "France" },
  { code: "GB", label: "United Kingdom" },
  { code: "IE", label: "Ireland" },
  { code: "IN", label: "India" },
  { code: "LK", label: "Sri Lanka" },
  { code: "NZ", label: "New Zealand" },
  { code: "US", label: "United States" },
  { code: "ZA", label: "South Africa" },
];
