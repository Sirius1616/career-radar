import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { setToken } from "../api";

const links = [
  { to: "/", label: "Overview" },
  { to: "/profile", label: "Profile" },
  { to: "/preferences", label: "Preferences" },
  { to: "/jobs", label: "Jobs" },
  { to: "/applications", label: "Applications" },
  { to: "/activity", label: "Activity" },
];

export default function DashboardLayout() {
  const navigate = useNavigate();
  return (
    <div>
      <header>
        <strong>Career Radar</strong>
        <nav>
          {links.map((link) => (
            <NavLink key={link.to} to={link.to} end={link.to === "/"}>
              {link.label}
            </NavLink>
          ))}
        </nav>
        <button
          type="button"
          onClick={() => {
            setToken(null);
            navigate("/login");
          }}
        >
          Log out
        </button>
      </header>
      <main>
        <Outlet />
      </main>
    </div>
  );
}
