import { FormEvent, useState } from "react";
import { Link } from "react-router-dom";
import { api, setToken, ApiError } from "../api";

interface TokenResponse {
  access_token: string;
}

export default function RegisterPage({ onAuthed }: { onAuthed: () => void }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const result = await api<TokenResponse>("/auth/register", {
        method: "POST",
        body: { email, password },
      });
      setToken(result.access_token);
      onAuthed();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Network error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit}>
      <h1>Register</h1>
      {error && <p role="alert">{error}</p>}
      <label>
        Email
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
      </label>
      <label>
        Password (min 12 characters)
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          minLength={12}
          required
        />
      </label>
      <button type="submit" disabled={busy}>
        {busy ? "Creating account…" : "Register"}
      </button>
      <p>
        Already registered? <Link to="/login">Log in</Link>
      </p>
    </form>
  );
}
