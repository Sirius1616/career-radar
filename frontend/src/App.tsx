import { useEffect, useState } from "react";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

interface Health {
  status: string;
  database: string;
}

export default function App() {
  const [health, setHealth] = useState<Health | null>(null);

  useEffect(() => {
    fetch(`${API_URL}/healthz`)
      .then((r) => r.json())
      .then(setHealth)
      .catch(() => setHealth(null));
  }, []);

  return (
    <main>
      <h1>Career Radar</h1>
      <p>
        API status: {health ? `${health.status} (database: ${health.database})` : "unreachable"}
      </p>
    </main>
  );
}
