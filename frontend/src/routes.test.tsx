import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import AppRoutes from "./routes";

describe("routing and auth redirect", () => {
  it("redirects logged-out users from protected routes to /login", () => {
    localStorage.removeItem("career_radar_token");
    render(
      <MemoryRouter initialEntries={["/jobs"]}>
        <AppRoutes />
      </MemoryRouter>,
    );
    expect(screen.getByRole("heading", { name: "Log in" })).toBeInTheDocument();
  });

  it("renders the protected overview route after login", () => {
    localStorage.setItem("career_radar_token", "dummy-token");
    render(
      <MemoryRouter initialEntries={["/"]}>
        <AppRoutes />
      </MemoryRouter>,
    );
    expect(screen.getByRole("heading", { name: "Overview" })).toBeInTheDocument();
  });

  it("redirects logged-in users away from /login", () => {
    localStorage.setItem("career_radar_token", "dummy-token");
    render(
      <MemoryRouter initialEntries={["/login"]}>
        <AppRoutes />
      </MemoryRouter>,
    );
    expect(screen.getByRole("heading", { name: "Overview" })).toBeInTheDocument();
  });

  it("shows the register page for logged-out users", () => {
    localStorage.removeItem("career_radar_token");
    render(
      <MemoryRouter initialEntries={["/register"]}>
        <AppRoutes />
      </MemoryRouter>,
    );
    expect(
      screen.getByRole("heading", { name: "Register" }),
    ).toBeInTheDocument();
  });
});
