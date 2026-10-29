import React from "react";
import {
  ShieldCheck,
  Database,
  RotateCcw,
  BarChart3,
  ShoppingBag,
  MessageSquare,
  FileText,
  Layers,
  History,
  LogOut,
  Sparkles,
  ArrowRightLeft
} from "lucide-react";
import type { HealthResponse, CatalogueStatusResponse, User } from "../types";

interface HeaderProps {
  health?: HealthResponse | null;
  catalogueStatus?: CatalogueStatusResponse | null;
  currentUser: User | null;
  currentView: string;
  onSelectView: (view: string) => void;
  onResetChat: () => void;
  onOpenEvaluation: () => void;
  onOpenAuth: (defaultTab?: "login" | "signup" | "owner") => void;
  onLogout: () => void;
  onQuickSwitchRole: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  catalogueStatus,
  currentUser,
  currentView,
  onSelectView,
  onResetChat,
  onOpenEvaluation,
  onOpenAuth,
  onLogout,
  onQuickSwitchRole,
}) => {
  const isOwner = currentUser?.role === "OWNER";


  const customerNavItems = [
    { id: "chat", label: "Assistant", icon: Sparkles },
    { id: "browse", label: "Browse Products", icon: ShoppingBag },
    { id: "feedback", label: "My Feedback", icon: MessageSquare },
    { id: "policy", label: "Store Policies", icon: FileText },
  ];

  const ownerNavItems = [
    { id: "owner-dashboard", label: "Dashboard", icon: Layers },
    { id: "owner-catalogue", label: "Catalogue Upload", icon: Database },
    { id: "owner-products", label: "Products", icon: ShoppingBag },
    { id: "owner-feedback", label: "Customer Feedback", icon: MessageSquare },
    { id: "owner-policy", label: "Policies", icon: FileText },
    { id: "owner-audit", label: "Audit Trail", icon: History },
  ];

  const navItems = isOwner ? ownerNavItems : customerNavItems;

  return (
    <header className="bg-white border-b border-slate-200 sticky top-0 z-30 shadow-xs">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Top row: Brand & Actions */}
        <div className="h-16 flex items-center justify-between">
          {/* Brand Identity */}
          <div className="flex items-center space-x-3 cursor-pointer" onClick={() => onSelectView(isOwner ? "owner-dashboard" : "chat")}>
            <div className="h-10 w-10 rounded-xl bg-gradient-to-tr from-blue-700 via-indigo-600 to-violet-600 flex items-center justify-center text-white shadow-sm ring-2 ring-indigo-50">
              <ShieldCheck className="h-6 w-6 stroke-[2.2]" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <span className="text-xl font-bold tracking-tight text-slate-900">
                  TruthCart <span className="text-indigo-600">AI</span>
                </span>
                <span className="text-[10px] font-bold uppercase px-2 py-0.5 rounded-full bg-slate-100 text-slate-700 border border-slate-200">
                  Team TalentX
                </span>
              </div>
              <p className="text-[11px] text-slate-500 font-medium hidden sm:block">
                The Shopping Assistant That Doesn't Lie
              </p>
            </div>
          </div>

          {/* Center / Right Control Panel */}
          <div className="flex items-center space-x-2.5">
            {catalogueStatus && (
              <div className="hidden xl:flex items-center space-x-1.5 px-2.5 py-1 rounded-lg border text-xs font-medium bg-slate-50 border-slate-200">
                <Database className="h-3.5 w-3.5 text-slate-500" />
                <span className="text-slate-600">Catalogue:</span>
                <span className="font-semibold text-slate-800">
                  {catalogueStatus.status}
                </span>
              </div>
            )}

            {/* Conditional Portal Switcher: Strictly rendered during active demo sessions */}
            {currentUser?.is_demo && (
              <button
                onClick={onQuickSwitchRole}
                id="switch-portal-demo-btn"
                className="flex items-center space-x-1.5 px-3 py-1.5 rounded-xl bg-purple-50 hover:bg-purple-100 text-purple-700 border border-purple-200 text-xs font-semibold transition-colors cursor-pointer"
                title={`Switch demo session to ${isOwner ? "Customer Shopping" : "Store Owner"} Portal`}
              >
                <ArrowRightLeft className="h-3.5 w-3.5" />
                <span>Switch to {isOwner ? "Customer" : "Owner"} View</span>
              </button>
            )}

            {/* Evaluation Suite Button */}
            <button
              onClick={onOpenEvaluation}
              id="evaluation-suite-btn"
              className="flex items-center space-x-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold bg-indigo-50 hover:bg-indigo-100 text-indigo-700 border border-indigo-200 transition-colors cursor-pointer"
              title="Open benchmark test suite and metrics"
            >
              <BarChart3 className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">Evaluation Suite</span>
            </button>

            {/* Reset Chat (only when in chat view) */}
            {currentView === "chat" && (
              <button
                onClick={onResetChat}
                id="reset-chat-btn"
                className="flex items-center space-x-1 px-2.5 py-1.5 rounded-xl text-xs font-medium text-slate-600 hover:text-slate-900 hover:bg-slate-100 border border-slate-200 transition-colors cursor-pointer"
                title="Reset conversation constraints"
              >
                <RotateCcw className="h-3.5 w-3.5" />
                <span className="hidden sm:inline">Reset</span>
              </button>
            )}

            {/* User Profile / Auth State */}
            {currentUser ? (
              <div className="flex items-center space-x-2 pl-2 border-l border-slate-200">
                <div className="text-right hidden sm:block">
                  <span className="text-xs font-bold text-slate-900 block truncate max-w-[130px]">
                    {currentUser.full_name}
                  </span>
                  <div className="flex items-center justify-end space-x-1">
                    <span
                      className={`text-[10px] font-bold uppercase tracking-wider px-1.5 py-0.2 rounded ${
                        isOwner
                          ? "bg-purple-100 text-purple-800"
                          : "bg-blue-100 text-blue-800"
                      }`}
                    >
                      {currentUser.role}
                    </span>
                    {currentUser.is_demo && (
                      <span className="text-[9px] font-extrabold uppercase px-1 rounded bg-amber-100 text-amber-800 border border-amber-200">
                        Demo
                      </span>
                    )}
                  </div>
                </div>
                <button
                  onClick={onLogout}
                  className="p-2 rounded-xl text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition-colors cursor-pointer"
                  title={currentUser.is_demo ? "Exit Demo Session" : "Sign out of TruthCart AI"}
                >
                  <LogOut className="h-4 w-4" />
                </button>
              </div>
            ) : (
              <div className="flex items-center space-x-1.5 pl-2 border-l border-slate-200">
                <button
                  onClick={() => onOpenAuth("login")}
                  id="header-try-demo-btn"
                  className="hidden sm:flex items-center space-x-1 px-2.5 py-1.5 rounded-xl text-xs font-semibold text-indigo-700 bg-indigo-50 hover:bg-indigo-100 border border-indigo-200 transition-colors cursor-pointer"
                  title="Explore TruthCart AI without credentials"
                >
                  <Sparkles className="h-3.5 w-3.5 text-indigo-600" />
                  <span>Try Demo</span>
                </button>
                <button
                  onClick={() => onOpenAuth("login")}
                  className="px-3 py-1.5 rounded-xl text-xs font-semibold text-slate-700 hover:bg-slate-100 transition-colors cursor-pointer"
                >
                  Sign In
                </button>
                <button
                  onClick={() => onOpenAuth("owner")}
                  className="px-3 py-1.5 rounded-xl text-xs font-semibold text-white bg-purple-700 hover:bg-purple-800 transition-colors shadow-2xs cursor-pointer"
                >
                  Owner Portal
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Bottom row: Navigation Tabs */}
        <div className="flex items-center space-x-1 overflow-x-auto py-2 border-t border-slate-100 scrollbar-none text-xs font-semibold">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = currentView === item.id;
            return (
              <button
                key={item.id}
                onClick={() => onSelectView(item.id)}
                className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-xl transition-all cursor-pointer whitespace-nowrap ${
                  isActive
                    ? isOwner
                      ? "bg-purple-700 text-white shadow-2xs"
                      : "bg-indigo-600 text-white shadow-2xs"
                    : "text-slate-600 hover:text-slate-900 hover:bg-slate-100"
                }`}
              >
                <Icon className="h-3.5 w-3.5" />
                <span>{item.label}</span>
              </button>
            );
          })}
        </div>
      </div>
    </header>
  );
};
