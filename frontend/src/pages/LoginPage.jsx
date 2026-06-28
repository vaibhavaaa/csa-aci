import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

const API = import.meta.env.VITE_API_URL || ""; // empty = relative to current origin

export default function LoginPage({ onLogin }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  async function handleLogin() {
    if (!username || !password) {
      setError("Username and password required.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${API}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams({ username, password }),
      });
      if (!res.ok) {
        const data = await res.json();
        setError(data.detail || "Login failed.");
        setLoading(false);
        return;
      }
      const data = await res.json();
      onLogin(data.access_token);
      navigate("/overview");
    } catch {
      setError("Cannot reach server. Is the backend running?");
      setLoading(false);
    }
  }

  function handleKeyDown(e) {
    if (e.key === "Enter") handleLogin();
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center">
      <div className="aurora" aria-hidden="true">
        <div className="blob b1" />
        <div className="blob b2" />
        <div className="blob b3" />
      </div>

      <Card className="relative z-10 w-full max-w-[420px] p-10">
        <div className="mb-9 flex items-center gap-3">
          <div className="grid h-11 w-11 place-items-center rounded-xl bg-gradient-to-br from-cyan to-violet text-lg font-extrabold text-[#06060f] shadow-[0_0_22px_rgba(0,229,255,0.35)]">
            C
          </div>
          <div>
            <div className="text-xl font-extrabold tracking-wide text-ink">CSA-ACI</div>
            <div className="text-[10px] uppercase tracking-widest text-faint">
              Cognitive Constraint Engine
            </div>
          </div>
        </div>

        <div className="mb-4">
          <div className="mb-2 text-[11px] uppercase tracking-wider text-muted">Username</div>
          <Input
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="enter username"
          />
        </div>

        <div className="mb-6">
          <div className="mb-2 text-[11px] uppercase tracking-wider text-muted">Password</div>
          <Input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="enter password"
          />
        </div>

        {error && (
          <div className="mb-5 rounded-lg border border-bad/30 bg-bad/10 px-3.5 py-2.5 text-xs text-bad">
            ✗ {error}
          </div>
        )}

        <Button variant="primary" className="w-full" onClick={handleLogin} disabled={loading}>
          {loading ? "Authenticating…" : "→ Login"}
        </Button>

        <div className="mt-5 text-center text-[11px] text-faint">
          No account? Use POST /auth/register to create one.
        </div>
      </Card>
    </div>
  );
}