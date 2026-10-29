import React, { useState } from "react";
import { X, ShieldCheck, Lock, Mail, User, Sparkles, AlertCircle, ShoppingBag, ArrowRight } from "lucide-react";
import { login, signup, ownerLogin, createDemoSession, setStoredToken, setStoredUser } from "../services/api";
import type { User as UserType } from "../types";

interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (user: UserType) => void;
  defaultTab?: "login" | "signup" | "owner";
}

export const AuthModal: React.FC<AuthModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
  defaultTab = "login",
}) => {
  const [tab, setTab] = useState<"login" | "signup" | "owner">(defaultTab);
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsLoading(true);

    try {
      if (tab === "signup") {
        const resp = await signup(fullName, email, password);
        onSuccess(resp.user);
        onClose();
      } else if (tab === "owner") {
        const resp = await ownerLogin(email, password);
        onSuccess(resp.user);
        onClose();
      } else {
        const resp = await login(email, password);
        onSuccess(resp.user);
        onClose();
      }
    } catch (err: any) {
      setError(err.message || "Authentication failed. Please check your credentials.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleDemoCustomerLogin = async () => {
    setError(null);
    setIsLoading(true);
    try {
      const resp = await createDemoSession("CUSTOMER");
      onSuccess(resp.user);
      onClose();
    } catch {
      try {
        const resp = await login("customer@truthcart.ai", "Customer123!");
        onSuccess(resp.user);
        onClose();
      } catch {
        // Resilient in-browser fallback so demo never fails even during backend restart
        const fallbackDemoUser: UserType = {
          id: "demo-customer-session",
          email: "customer@truthcart.ai",
          full_name: "Priya Sharma (Shopper Demo)",
          role: "CUSTOMER",
          is_demo: true,
          created_at: new Date().toISOString(),
        };
        setStoredToken("demo-customer-offline-token");
        setStoredUser(fallbackDemoUser);
        onSuccess(fallbackDemoUser);
        onClose();
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleDemoOwnerLogin = async () => {
    setError(null);
    setIsLoading(true);
    try {
      const resp = await createDemoSession("OWNER");
      onSuccess(resp.user);
      onClose();
    } catch {
      try {
        const resp = await ownerLogin("owner@truthcart.ai", "AdminTruthCart2026!");
        onSuccess(resp.user);
        onClose();
      } catch {
        // Resilient in-browser fallback so demo never fails even during backend restart
        const fallbackOwnerUser: UserType = {
          id: "demo-owner-session",
          email: "demo-owner@truthcart.ai",
          full_name: "Store Owner (Demo)",
          role: "OWNER",
          is_demo: true,
          created_at: new Date().toISOString(),
        };
        setStoredToken("demo-owner-offline-token");
        setStoredUser(fallbackOwnerUser);
        onSuccess(fallbackOwnerUser);
        onClose();
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs animate-fade-in">
      <div className="bg-white rounded-2xl max-w-md w-full shadow-2xl border border-slate-200 overflow-hidden">
        {/* Header */}
        <div className="bg-gradient-to-r from-blue-700 via-indigo-600 to-violet-700 p-6 text-white relative">
          <button
            onClick={onClose}
            className="absolute top-4 right-4 p-1.5 rounded-lg bg-white/10 hover:bg-white/20 text-white transition-colors cursor-pointer"
          >
            <X className="h-5 w-5" />
          </button>
          <div className="flex items-center space-x-2.5 mb-1.5">
            <div className="p-2 rounded-xl bg-white/10 backdrop-blur-xs">
              <ShieldCheck className="h-6 w-6 text-indigo-200" />
            </div>
            <h3 className="text-xl font-bold tracking-tight">TruthCart AI Account</h3>
          </div>
          <p className="text-xs text-indigo-100">
            {tab === "owner"
              ? "Store Owner Portal — Manage catalogue, policies, and verified facts."
              : "Shopper Experience — Browse verified products with proof-backed answers."}
          </p>
        </div>

        {/* Tab Switcher */}
        <div className="flex border-b border-slate-200 bg-slate-50 text-xs font-semibold">
          <button
            onClick={() => { setTab("login"); setError(null); }}
            className={`flex-1 py-3 text-center border-b-2 transition-colors cursor-pointer ${
              tab === "login"
                ? "border-indigo-600 text-indigo-700 bg-white"
                : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            Customer Login
          </button>
          <button
            onClick={() => { setTab("signup"); setError(null); }}
            className={`flex-1 py-3 text-center border-b-2 transition-colors cursor-pointer ${
              tab === "signup"
                ? "border-indigo-600 text-indigo-700 bg-white"
                : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            Sign Up
          </button>
          <button
            onClick={() => { setTab("owner"); setError(null); }}
            className={`flex-1 py-3 text-center border-b-2 transition-colors cursor-pointer ${
              tab === "owner"
                ? "border-purple-600 text-purple-700 bg-white font-bold"
                : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            Owner Portal
          </button>
        </div>

        {/* Body */}
        <div className="p-6 space-y-4">
          {tab === "owner" && (
            <div className="p-2.5 rounded-xl bg-purple-50 border border-purple-200 text-purple-900 text-xs flex items-center justify-between">
              <div>
                <span className="font-bold">Store Owner Account</span>
                <div className="text-[11px] text-purple-700">owner@truthcart.ai &bull; AdminTruthCart2026!</div>
              </div>
              <button
                type="button"
                onClick={() => {
                  setEmail("owner@truthcart.ai");
                  setPassword("AdminTruthCart2026!");
                  setError(null);
                }}
                className="px-2.5 py-1 text-[11px] font-semibold bg-purple-600 hover:bg-purple-700 text-white rounded-lg transition-colors cursor-pointer shrink-0 ml-2"
              >
                Auto-fill
              </button>
            </div>
          )}

          {tab === "login" && (
            <div className="p-2.5 rounded-xl bg-indigo-50 border border-indigo-200 text-indigo-900 text-xs flex items-center justify-between">
              <div>
                <span className="font-bold">Customer Account</span>
                <div className="text-[11px] text-indigo-700">customer@truthcart.ai &bull; Customer123!</div>
              </div>
              <button
                type="button"
                onClick={() => {
                  setEmail("customer@truthcart.ai");
                  setPassword("Customer123!");
                  setError(null);
                }}
                className="px-2.5 py-1 text-[11px] font-semibold bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg transition-colors cursor-pointer shrink-0 ml-2"
              >
                Auto-fill
              </button>
            </div>
          )}

          {error && (
            <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs flex items-start space-x-2">
              <AlertCircle className="h-4 w-4 shrink-0 mt-0.5 text-rose-500" />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-3.5">
            {tab === "signup" && (
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Full Name
                </label>
                <div className="relative">
                  <User className="h-4 w-4 text-slate-400 absolute left-3 top-3" />
                  <input
                    type="text"
                    required
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    placeholder="e.g. Priya Sharma"
                    className="w-full pl-9 pr-3 py-2 text-xs rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-500 bg-white text-slate-900"
                  />
                </div>
              </div>
            )}

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Email Address
              </label>
              <div className="relative">
                <Mail className="h-4 w-4 text-slate-400 absolute left-3 top-3" />
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder={tab === "owner" ? "owner@truthcart.ai" : "you@example.com"}
                  className="w-full pl-9 pr-3 py-2 text-xs rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-500 bg-white text-slate-900"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Password
              </label>
              <div className="relative">
                <Lock className="h-4 w-4 text-slate-400 absolute left-3 top-3" />
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full pl-9 pr-3 py-2 text-xs rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-500 bg-white text-slate-900"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className={`w-full py-2.5 px-4 rounded-xl font-semibold text-xs text-white shadow-sm transition-all cursor-pointer ${
                tab === "owner"
                  ? "bg-purple-700 hover:bg-purple-800"
                  : "bg-indigo-600 hover:bg-indigo-700"
              } disabled:opacity-50`}
            >
              {isLoading
                ? "Authenticating..."
                : tab === "signup"
                ? "Create Customer Account"
                : tab === "owner"
                ? "Log In to Owner Portal"
                : "Log In as Customer"}
            </button>
          </form>

          {/* Explore TruthCart AI - Try Demo Section */}
          <div className="pt-4 border-t border-slate-200">
            <div className="text-center mb-2.5">
              <span className="text-xs font-bold text-slate-800 block">
                Explore TruthCart AI
              </span>
              <p className="text-[11px] text-slate-500 mt-0.5">
                Instant interactive access without registration or credentials
              </p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
              <button
                type="button"
                id="try-customer-demo-btn"
                onClick={handleDemoCustomerLogin}
                disabled={isLoading}
                className="group p-3 rounded-xl border border-indigo-200 bg-gradient-to-br from-indigo-50/80 to-blue-50/50 hover:from-indigo-100 hover:to-blue-100 text-left transition-all hover:shadow-xs cursor-pointer border-dashed hover:border-solid hover:border-indigo-400"
              >
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center space-x-1.5 text-indigo-700 font-bold text-xs">
                    <ShoppingBag className="h-4 w-4 shrink-0 text-indigo-600" />
                    <span>Try Customer Demo</span>
                  </div>
                  <ArrowRight className="h-3 w-3 text-indigo-400 group-hover:translate-x-0.5 transition-transform" />
                </div>
                <p className="text-[10px] text-slate-600 leading-tight">
                  Explore the customer shopping experience.
                </p>
              </button>

              <button
                type="button"
                id="try-owner-demo-btn"
                onClick={handleDemoOwnerLogin}
                disabled={isLoading}
                className="group p-3 rounded-xl border border-purple-200 bg-gradient-to-br from-purple-50/80 to-violet-50/50 hover:from-purple-100 hover:to-violet-100 text-left transition-all hover:shadow-xs cursor-pointer border-dashed hover:border-solid hover:border-purple-400"
              >
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center space-x-1.5 text-purple-700 font-bold text-xs">
                    <Sparkles className="h-4 w-4 shrink-0 text-purple-600" />
                    <span>Try Owner Demo</span>
                  </div>
                  <ArrowRight className="h-3 w-3 text-purple-400 group-hover:translate-x-0.5 transition-transform" />
                </div>
                <p className="text-[10px] text-slate-600 leading-tight">
                  Explore the store owner dashboard and management features.
                </p>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
