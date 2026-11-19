import { FormEvent, useEffect, useState } from "react";
import { api, ApiError } from "../api";

interface Preferences {
  job_titles: string[];
  required_skills: string[];
  min_experience_years: number | null;
  max_experience_years: number | null;
  countries: string[];
  cities: string[];
  remote_ok: boolean;
  hybrid_ok: boolean;
  onsite_ok: boolean;
  relocation_ok: boolean;
  visa_sponsorship: string | null;
  min_salary: number | null;
  employment_type: string | null;
  max_posting_age_days: number | null;
  min_match_score: number | null;
  lookback_window: string | null;
  lookback_from: string | null;
  lookback_to: string | null;
}

const EMPTY: Preferences = {
  job_titles: [],
  required_skills: [],
  min_experience_years: null,
  max_experience_years: null,
  countries: [],
  cities: [],
  remote_ok: false,
  hybrid_ok: false,
  onsite_ok: false,
  relocation_ok: false,
  visa_sponsorship: null,
  min_salary: null,
  employment_type: null,
  max_posting_age_days: null,
  min_match_score: null,
  lookback_window: "30d",
  lookback_from: null,
  lookback_to: null,
};

const LOOKBACK_OPTIONS = ["24h", "7d", "14d", "30d", "90d", "custom"];

function listToString(value: string[]): string {
  return value.join(", ");
}

function stringToList(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function numberOrNull(value: string): number | null {
  return value === "" ? null : Number(value);
}

export default function PreferencesPage() {
  const [prefs, setPrefs] = useState<Preferences>(EMPTY);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api<Preferences>("/preferences")
      .then(setPrefs)
      .catch((err: ApiError) => {
        if (err.status !== 404) setError(err.message);
      });
  }, []);

  function update(patch: Partial<Preferences>) {
    setPrefs((current) => ({ ...current, ...patch }));
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setStatus(null);
    setError(null);
    try {
      const saved = await api<Preferences>("/preferences", {
        method: "PUT",
        body: prefs,
      });
      setPrefs(saved);
      setStatus("Preferences saved.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Network error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit}>
      <h2>Job preferences</h2>
      {status && <p role="status">{status}</p>}
      {error && <p role="alert">{error}</p>}

      <label>
        Job titles (comma-separated)
        <input
          value={listToString(prefs.job_titles)}
          onChange={(e) => update({ job_titles: stringToList(e.target.value) })}
        />
      </label>
      <label>
        Required skills (comma-separated)
        <input
          value={listToString(prefs.required_skills)}
          onChange={(e) => update({ required_skills: stringToList(e.target.value) })}
        />
      </label>
      <label>
        Countries (comma-separated)
        <input
          value={listToString(prefs.countries)}
          onChange={(e) => update({ countries: stringToList(e.target.value) })}
        />
      </label>
      <label>
        Cities (comma-separated)
        <input
          value={listToString(prefs.cities)}
          onChange={(e) => update({ cities: stringToList(e.target.value) })}
        />
      </label>

      <label>
        Min experience (years)
        <input
          type="number"
          min={0}
          value={prefs.min_experience_years ?? ""}
          onChange={(e) => update({ min_experience_years: numberOrNull(e.target.value) })}
        />
      </label>
      <label>
        Max experience (years)
        <input
          type="number"
          min={0}
          value={prefs.max_experience_years ?? ""}
          onChange={(e) => update({ max_experience_years: numberOrNull(e.target.value) })}
        />
      </label>
      <label>
        Minimum salary
        <input
          type="number"
          min={0}
          value={prefs.min_salary ?? ""}
          onChange={(e) => update({ min_salary: numberOrNull(e.target.value) })}
        />
      </label>
      <label>
        Maximum posting age (days)
        <input
          type="number"
          min={1}
          max={365}
          value={prefs.max_posting_age_days ?? ""}
          onChange={(e) => update({ max_posting_age_days: numberOrNull(e.target.value) })}
        />
      </label>
      <label>
        Minimum match score
        <input
          type="number"
          min={0}
          max={100}
          value={prefs.min_match_score ?? ""}
          onChange={(e) => update({ min_match_score: numberOrNull(e.target.value) })}
        />
      </label>

      <label>
        Visa sponsorship
        <select
          value={prefs.visa_sponsorship ?? ""}
          onChange={(e) => update({ visa_sponsorship: e.target.value || null })}
        >
          <option value="">Not specified</option>
          <option value="not_required">Not required</option>
          <option value="preferred">Preferred</option>
          <option value="required">Required</option>
        </select>
      </label>
      <label>
        Employment type
        <select
          value={prefs.employment_type ?? ""}
          onChange={(e) => update({ employment_type: e.target.value || null })}
        >
          <option value="">Not specified</option>
          <option value="full_time">Full time</option>
          <option value="part_time">Part time</option>
          <option value="contract">Contract</option>
          <option value="internship">Internship</option>
        </select>
      </label>
      <label>
        Historical lookback window
        <select
          value={prefs.lookback_window ?? ""}
          onChange={(e) => update({ lookback_window: e.target.value || null })}
        >
          {LOOKBACK_OPTIONS.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
      </label>
      {prefs.lookback_window === "custom" && (
        <>
          <label>
            Lookback from
            <input
              type="date"
              value={prefs.lookback_from ?? ""}
              onChange={(e) => update({ lookback_from: e.target.value || null })}
            />
          </label>
          <label>
            Lookback to
            <input
              type="date"
              value={prefs.lookback_to ?? ""}
              onChange={(e) => update({ lookback_to: e.target.value || null })}
            />
          </label>
        </>
      )}

      <fieldset>
        <legend>Work arrangement</legend>
        {(
          [
            ["remote_ok", "Remote"],
            ["hybrid_ok", "Hybrid"],
            ["onsite_ok", "On-site"],
            ["relocation_ok", "Relocation"],
          ] as const
        ).map(([key, label]) => (
          <label key={key}>
            <input
              type="checkbox"
              checked={prefs[key]}
              onChange={(e) => update({ [key]: e.target.checked })}
            />
            {label}
          </label>
        ))}
      </fieldset>

      <button type="submit" disabled={busy}>
        {busy ? "Saving…" : "Save preferences"}
      </button>
    </form>
  );
}
