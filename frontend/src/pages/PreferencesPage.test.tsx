import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import PreferencesPage from "./PreferencesPage";

const saved = {
  job_titles: ["Backend Engineer"],
  required_skills: ["Python"],
  min_experience_years: 2,
  max_experience_years: 10,
  countries: ["United Kingdom"],
  cities: ["London"],
  remote_ok: true,
  hybrid_ok: false,
  onsite_ok: false,
  relocation_ok: true,
  visa_sponsorship: "required",
  min_salary: 45000,
  employment_type: "full_time",
  max_posting_age_days: 30,
  min_match_score: 70,
  lookback_window: "custom",
  lookback_from: "2026-01-01",
  lookback_to: "2026-02-01",
  user_id: "u1",
};

function mockApi(handler: (path: string, init: RequestInit | undefined) => Promise<Response>) {
  vi.stubGlobal("fetch", vi.fn(handler));
}

beforeEach(() => {
  localStorage.setItem("career_radar_token", "dummy");
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("PreferencesPage", () => {
  it("loads existing preferences and shows the custom range fields", async () => {
    mockApi(() =>
      Promise.resolve(
        new Response(JSON.stringify(saved), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );
    render(
      <MemoryRouter>
        <PreferencesPage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(
        screen.getByDisplayValue("Backend Engineer"),
      ).toBeInTheDocument();
    });
    expect(screen.getByDisplayValue("2026-01-01")).toBeInTheDocument();
  });

  it("submits edited preferences and shows the saved status", async () => {
    let sentBody: Record<string, unknown> | undefined;
    mockApi((_path, init) => {
      if (init?.method === "PUT") {
        sentBody = JSON.parse(init.body as string);
        return Promise.resolve(
          new Response(JSON.stringify(saved), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
        );
      }
      return Promise.resolve(
        new Response(JSON.stringify(saved), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
    });
    render(
      <MemoryRouter>
        <PreferencesPage />
      </MemoryRouter>,
    );
    await waitFor(() => screen.getByDisplayValue("Backend Engineer"));
    fireEvent.change(screen.getByDisplayValue("Backend Engineer"), {
      target: { value: "Backend Engineer, Platform Engineer" },
    });
    await userEvent.click(screen.getByRole("button", { name: /save/i }));
    await waitFor(() =>
      expect(screen.getByRole("status")).toHaveTextContent("Preferences saved."),
    );
    expect(sentBody?.job_titles).toEqual(["Backend Engineer", "Platform Engineer"]);
    expect(sentBody?.visa_sponsorship).toBe("required");
  });

  it("shows server validation errors", async () => {
    mockApi((_path, _init) =>
      Promise.resolve(
        new Response(
          JSON.stringify({ detail: "min_experience_years cannot exceed max_experience_years" }),
          { status: 422, headers: { "Content-Type": "application/json" } },
        ),
      ),
    );
    render(
      <MemoryRouter>
        <PreferencesPage />
      </MemoryRouter>,
    );
    await waitFor(() => screen.getByRole("button", { name: /save/i }));
    await userEvent.click(screen.getByRole("button", { name: /save/i }));
    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(/min_experience_years/),
    );
  });
});
