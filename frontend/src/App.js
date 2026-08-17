import "@/App.css";
import { BrowserRouter, Routes, Route, Outlet } from "react-router-dom";
import { AuthProvider } from "@/lib/auth";
import { Toaster } from "@/components/ui/sonner";
import Header from "@/components/Header";
import Landing from "@/pages/Landing";
import ToolPage from "@/pages/Tool";
import Auth from "@/pages/Auth";
import Dashboard from "@/pages/Dashboard";
import Pricing from "@/pages/Pricing";
import Unlocked from "@/pages/Unlocked";
import AuthCallback from "@/pages/AuthCallback";
import { useEffect } from "react";

function Shell() {
  useEffect(() => {
    if (localStorage.getItem("ughpdf_theme") === "dark") document.documentElement.classList.add("dark");
  }, []);
  return (
    <div className="App noise-bg min-h-screen">
      <Header />
      <main className="relative z-10">
        <Outlet />
      </main>
      <Toaster position="top-right" richColors />
    </div>
  );
}

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<Shell />}>
            <Route path="/" element={<Landing />} />
            <Route path="/t/:id" element={<ToolPage />} />
            <Route path="/login" element={<Auth mode="login" />} />
            <Route path="/signup" element={<Auth mode="signup" />} />
            <Route path="/auth/callback" element={<AuthCallback />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/pricing" element={<Pricing />} />
            <Route path="/unlocked" element={<Unlocked />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
