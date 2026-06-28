import { useState } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import LoginPage from "@/pages/LoginPage";
import AppLayout from "@/components/AppLayout";
import { DashboardProvider } from "@/context/DashboardContext";
import Overview from "@/pages/Overview";
import LiveControl from "@/pages/LiveControl";
import Simulation from "@/pages/Simulation";
import Experiments from "@/pages/Experiments";

export default function App() {
  const [token, setToken] = useState("");

  return (
    <BrowserRouter>
      {token ? (
        <DashboardProvider token={token} onLogout={() => setToken("")}>
          <Routes>
            <Route element={<AppLayout />}>
              <Route path="/overview" element={<Overview />} />
              <Route path="/live" element={<LiveControl />} />
              <Route path="/simulation" element={<Simulation />} />
              <Route path="/experiments" element={<Experiments />} />
            </Route>
            <Route path="*" element={<Navigate to="/overview" replace />} />
          </Routes>
        </DashboardProvider>
      ) : (
        <Routes>
          <Route path="/login" element={<LoginPage onLogin={setToken} />} />
          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
      )}
    </BrowserRouter>
  );
}
