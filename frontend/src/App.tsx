import { useState, useEffect, useRef } from "react";
import {
  Send,
  Sparkles,
  ArrowRight,
  Mic,
  MicOff
} from "lucide-react";
import { Header } from "./components/Header";
import { ReadinessBanner } from "./components/ReadinessBanner";
import { ChatMessage } from "./components/ChatMessage";
import { EvidenceDrawer } from "./components/EvidenceDrawer";
import { EvaluationModal } from "./components/EvaluationModal";
import { AuthModal } from "./components/AuthModal";
import { FeedbackModal } from "./components/FeedbackModal";

import { ProductBrowseView } from "./components/ProductBrowseView";
import { MyFeedbackView } from "./components/MyFeedbackView";
import { PolicyView } from "./components/PolicyView";

import { OwnerDashboardView } from "./components/OwnerDashboardView";
import { OwnerCatalogueView } from "./components/OwnerCatalogueView";
import { OwnerProductsView } from "./components/OwnerProductsView";
import { OwnerFeedbackView } from "./components/OwnerFeedbackView";
import { OwnerPolicyView } from "./components/OwnerPolicyView";
import { OwnerAuditView } from "./components/OwnerAuditView";
import { fetchDemoCatalogueStatus, isDemoSession } from "./services/demoService";

import {
  fetchHealth,
  fetchCatalogueStatus,
  reloadCatalogue,
  sendChatMessage,
  fetchMe,
  getStoredUser,
  clearStoredToken,
  clearStoredUser,
  logout,
  login,
  ownerLogin,
  createDemoSession,
} from "./services/api";
import type {
  HealthResponse,
  CatalogueStatusResponse,
  ChatMessage as ChatMessageType,
  EvidenceObject,
  User,
} from "./types";

export function App() {
  const [currentUser, setCurrentUser] = useState<User | null>(getStoredUser());
  const [currentView, setCurrentView] = useState<string>("chat");

  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [catalogueStatus, setCatalogueStatus] = useState<CatalogueStatusResponse | null>(null);
  const [messages, setMessages] = useState<ChatMessageType[]>([]);
  const [inputMessage, setInputMessage] = useState<string>("");
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isDataLoading, setIsDataLoading] = useState<boolean>(false);
  const [conversationId, setConversationId] = useState<string | undefined>(undefined);
  const [error, setError] = useState<string | null>(null);

  // Evidence Drawer state
  const [selectedEvidence, setSelectedEvidence] = useState<{
    evidence: EvidenceObject;
    latencyMs?: number;
    retrievalStatus?: string;
    modelStatus?: string;
  } | null>(null);
  const [isEvidenceOpen, setIsEvidenceOpen] = useState<boolean>(false);

  // Modals
  const [isEvaluationOpen, setIsEvaluationOpen] = useState<boolean>(false);
  const [isAuthModalOpen, setIsAuthModalOpen] = useState<boolean>(false);
  const [authModalDefaultTab, setAuthModalDefaultTab] = useState<"login" | "signup" | "owner">("login");

  const [isFeedbackModalOpen, setIsFeedbackModalOpen] = useState<boolean>(false);
  const [feedbackPrefillSku, setFeedbackPrefillSku] = useState<string | undefined>(undefined);
  const [feedbackPrefillConv, setFeedbackPrefillConv] = useState<string | undefined>(undefined);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom of chat
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    if (currentView === "chat") {
      scrollToBottom();
    }
  }, [messages, isLoading, currentView]);

  // Initial load
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const demoParam = params.get("demo") || params.get("portal");
    if (demoParam) {
      const isOwnerDemo = demoParam.toLowerCase().includes("owner");
      const role = isOwnerDemo ? "OWNER" : "CUSTOMER";
      createDemoSession(role).then((resp) => {
        setCurrentUser(resp.user);
        if (role === "OWNER") {
          setCurrentView("owner-dashboard");
        } else {
          setCurrentView("browse");
        }
        loadAppStatus(true);
      }).catch(() => {
        const fallbackDemoUser: User = {
          id: isOwnerDemo ? "demo-owner-id" : "demo-customer-id",
          email: isOwnerDemo ? "demo-owner@truthcart.ai" : "customer@truthcart.ai",
          full_name: isOwnerDemo ? "TruthCart Store Owner (Demo)" : "Demo Shopper",
          role: role,
          is_demo: true,
          created_at: new Date().toISOString(),
        };
        setCurrentUser(fallbackDemoUser);
        setCurrentView(isOwnerDemo ? "owner-dashboard" : "browse");
        loadAppStatus(true);
      });
    } else {
      loadAppStatus();
      verifyAuth();
    }
  }, []);

  const verifyAuth = async () => {
    try {
      const user = await fetchMe();
      setCurrentUser(user);
    } catch {
      clearStoredToken();
      clearStoredUser();
      setCurrentUser(null);
    }
  };

  const loadAppStatus = async (isDemoOverride?: boolean) => {
    try {
      const activeIsDemo = Boolean(isDemoOverride ?? currentUser?.is_demo ?? isDemoSession());
      const [h, c] = await Promise.all([
        fetchHealth(),
        activeIsDemo ? fetchDemoCatalogueStatus() : fetchCatalogueStatus()
      ]);
      setHealth(h);
      setCatalogueStatus(c);
    } catch (err: any) {
      console.warn("Could not fetch status:", err.message);
    }
  };

  const handleToggleFixtures = async (enable: boolean) => {
    setIsDataLoading(true);
    try {
      const updatedCat = await reloadCatalogue(enable);
      setCatalogueStatus(updatedCat);
      const updatedHealth = await fetchHealth();
      setHealth(updatedHealth);
    } catch (err: any) {
      setError(err.message || "Failed to toggle fixtures.");
    } finally {
      setIsDataLoading(false);
    }
  };

  // Voice Input (Speech Recognition) state
  const [isListening, setIsListening] = useState(false);
  const recognitionRef = useRef<any>(null);

  const handleToggleVoiceInput = () => {
    const SpeechRecognition =
      (window as unknown as { SpeechRecognition?: any }).SpeechRecognition ||
      (window as unknown as { webkitSpeechRecognition?: any }).webkitSpeechRecognition;

    if (!SpeechRecognition) {
      setError("Speech recognition is not supported in this browser. Please use Google Chrome or Microsoft Edge.");
      return;
    }

    if (isListening) {
      if (recognitionRef.current) {
        recognitionRef.current.stop();
      }
      setIsListening(false);
      return;
    }

    try {
      const recognition = new SpeechRecognition();
      recognition.lang = "en-IN";
      recognition.interimResults = false;
      recognition.maxAlternatives = 1;

      recognition.onstart = () => setIsListening(true);
      recognition.onend = () => setIsListening(false);
      recognition.onerror = () => setIsListening(false);
      recognition.onresult = (event: any) => {
        const transcript = event.results?.[0]?.[0]?.transcript;
        if (transcript) {
          setInputMessage((prev) => (prev ? `${prev} ${transcript}` : transcript));
        }
      };

      recognitionRef.current = recognition;
      recognition.start();
    } catch {
      setIsListening(false);
    }
  };

  const handleSendMessage = async (queryText?: string) => {
    const textToSend = (queryText || inputMessage).trim();
    if (!textToSend || isLoading) return;

    setError(null);
    setInputMessage("");

    const userMsg: ChatMessageType = {
      id: `user-${Date.now()}`,
      sender: "user",
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      text: textToSend,
    };

    setMessages((prev) => [...prev, userMsg]);
    setIsLoading(true);

    try {
      const resp = await sendChatMessage(textToSend, conversationId);
      setConversationId(resp.conversation_id);

      const assistantMsg: ChatMessageType = {
        id: `assistant-${Date.now()}`,
        sender: "assistant",
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        text: resp.response_text,
        decision: resp.decision,
        products: resp.products,
        comparison_data: resp.comparison_data,
        citations: resp.citations,
        evidence: resp.evidence,
        clarification_question: resp.clarification_question,
        refusal_reason: resp.refusal_reason,
        retrieval_status: resp.retrieval_status,
        model_status: resp.model_status,
        latency_ms: resp.latency_ms,
        token_cost: resp.token_cost ?? 0.0,
      };

      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err: any) {
      setError(err.message || "An error occurred while communicating with TruthCart AI.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleResetChat = () => {
    setMessages([]);
    setConversationId(undefined);
    setError(null);
  };

  const handleOpenEvidence = (msg: ChatMessageType) => {
    if (msg.evidence) {
      setSelectedEvidence({
        evidence: msg.evidence,
        latencyMs: msg.latency_ms,
        retrievalStatus: msg.retrieval_status,
        modelStatus: msg.model_status,
      });
      setIsEvidenceOpen(true);
    }
  };

  const handleOpenReportFromMessage = (msg: ChatMessageType) => {
    // If message cited a product, prefill it
    const citedSku = msg.products && msg.products.length > 0 ? msg.products[0].product_id : undefined;
    setFeedbackPrefillSku(citedSku);
    setFeedbackPrefillConv(conversationId);
    if (!currentUser) {
      setAuthModalDefaultTab("login");
      setIsAuthModalOpen(true);
      return;
    }
    setIsFeedbackModalOpen(true);
  };

  const handleOpenReportForSku = (sku: string) => {
    setFeedbackPrefillSku(sku);
    setFeedbackPrefillConv(undefined);
    if (!currentUser) {
      setAuthModalDefaultTab("login");
      setIsAuthModalOpen(true);
      return;
    }
    setIsFeedbackModalOpen(true);
  };

  const handleQuickSwitchRole = async () => {
    if (!currentUser?.is_demo) return;
    setIsLoading(true);
    try {
      if (currentUser?.role === "OWNER") {
        // Switch to Customer Demo
        const resp = await createDemoSession("CUSTOMER");
        setCurrentUser(resp.user);
        setCurrentView("chat");
      } else {
        // Switch to Owner Demo
        const resp = await createDemoSession("OWNER");
        setCurrentUser(resp.user);
        setCurrentView("owner-dashboard");
      }
      await loadAppStatus();
    } catch (e) {
      console.error("Failed to switch demo role:", e);
      try {
        if (currentUser?.role === "OWNER") {
          const resp = await login("customer@truthcart.ai", "Customer123!");
          setCurrentUser({ ...resp.user, is_demo: true });
          setCurrentView("chat");
        } else {
          const resp = await ownerLogin("owner@truthcart.ai", "AdminTruthCart2026!");
          setCurrentUser({ ...resp.user, is_demo: true });
          setCurrentView("owner-dashboard");
        }
        await loadAppStatus();
      } catch (fbErr) {
        console.error("Fallback role switch error:", fbErr);
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleLogout = async () => {
    await logout();
    setCurrentUser(null);
    setCurrentView("chat");
  };

  const samplePrompts = [
    { label: "Price Lookup", query: "What is the price of TC-CAT01-001?" },
    { label: "Budget & In-Stock", query: "Show me products under ₹2,000 that are in stock" },
    { label: "Store Policy", query: "What is your return policy window?" },
    { label: "Comparison Test", query: "Compare TC-CAT01-001 and TC-CAT01-010" },
    { label: "Ambiguity Clarify", query: "Show me accessories" },
    { label: "Trust Test (Out of Catalogue)", query: "What is the discount on Sony PlayStation 5 Pro?" },
  ];

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col text-slate-800">
      {/* Universal Header */}
      <Header
        health={health}
        catalogueStatus={catalogueStatus}
        currentUser={currentUser}
        currentView={currentView}
        onSelectView={setCurrentView}
        onResetChat={handleResetChat}
        onOpenEvaluation={() => setIsEvaluationOpen(true)}
        onOpenAuth={(tab) => {
          setAuthModalDefaultTab(tab || "login");
          setIsAuthModalOpen(true);
        }}
        onLogout={handleLogout}
        onQuickSwitchRole={handleQuickSwitchRole}
      />

      {/* Demo Session Notice Banner (Strictly visible when currentUser is in demo mode) */}
      {currentUser?.is_demo && (
        <div className="bg-gradient-to-r from-indigo-700 via-purple-700 to-indigo-800 text-white text-xs px-4 py-2 shadow-2xs border-b border-indigo-500/30 animate-fade-in">
          <div className="max-w-7xl mx-auto flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <span className="font-extrabold uppercase tracking-wider text-[10px] bg-amber-400 text-slate-900 px-2 py-0.5 rounded-full shadow-2xs">
                Demo Session
              </span>
              <span className="hidden md:inline text-indigo-100">
                You are currently exploring the{" "}
                <strong className="text-white">
                  {currentUser.role === "OWNER" ? "Store Owner Portal" : "Customer Shopping Experience"}
                </strong>
                . Isolated demo data prevents modification of persistent production records.
              </span>
              <span className="md:hidden font-medium text-white">
                {currentUser.role === "OWNER" ? "Owner Demo Active" : "Customer Demo Active"}
              </span>
            </div>
            <div className="flex items-center space-x-3">
              <button
                onClick={handleQuickSwitchRole}
                id="banner-switch-demo-btn"
                className="text-amber-300 hover:text-amber-200 underline text-xs font-bold cursor-pointer transition-colors"
              >
                Switch to {currentUser.role === "OWNER" ? "Customer Demo" : "Owner Demo"}
              </button>
              <button
                onClick={handleLogout}
                id="banner-exit-demo-btn"
                className="bg-white/10 hover:bg-white/20 text-white px-2.5 py-1 rounded-lg text-[11px] font-semibold cursor-pointer transition-colors border border-white/20"
              >
                Exit Demo
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Customer Mode: Readiness Banner (only in customer chat view) */}
      {currentView === "chat" && (
        <ReadinessBanner
          catalogueStatus={catalogueStatus}
          onToggleFixtures={handleToggleFixtures}
          isLoading={isDataLoading}
        />
      )}

      {/* Main Content Router */}
      <main className="flex-1 flex flex-col">
        {/* CUSTOMER: Chat View */}
        {currentView === "chat" && (
          <div className="flex-1 max-w-5xl w-full mx-auto px-4 sm:px-6 py-6 flex flex-col justify-between">
            {messages.length === 0 ? (
              <div className="flex-1 flex flex-col items-center justify-center py-8 text-center max-w-2xl mx-auto space-y-8 animate-fade-in">
                {/* Hero Pill */}
                <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-indigo-50 border border-indigo-200 text-xs font-semibold text-indigo-700 shadow-2xs">
                  <Sparkles className="h-3.5 w-3.5" />
                  <span>Talent AP Mega Hackathon 2026 • Retail Track (Problem Statement R3)</span>
                </div>

                {/* Title & Tagline */}
                <div>
                  <h2 className="text-3xl sm:text-4xl font-extrabold text-slate-900 tracking-tight">
                    The Shopping Assistant That{" "}
                    <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-700 via-indigo-600 to-violet-600">
                      Doesn't Lie
                    </span>
                  </h2>
                  <p className="text-sm sm:text-base text-slate-600 mt-3 leading-relaxed">
                    Traditional AI shopping assistants invent prices, stock, and policies.{" "}
                    <strong>TruthCart AI</strong> answers only from verified catalogue records and store policies. If evidence is insufficient, it refuses or clarifies rather than guesses.
                  </p>
                </div>

                {/* Core Pillars */}
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3.5 w-full text-left">
                  <div className="p-4 rounded-xl bg-white border border-slate-200/90 shadow-2xs">
                    <span className="text-xs font-bold text-indigo-700 block mb-1">
                      1. Catalogue As Truth
                    </span>
                    <p className="text-xs text-slate-500 leading-relaxed">
                      Prices, availability, and specs come exclusively from verified ground-truth records.
                    </p>
                  </div>

                  <div className="p-4 rounded-xl bg-white border border-slate-200/90 shadow-2xs">
                    <span className="text-xs font-bold text-indigo-700 block mb-1">
                      2. Citation Enforcement
                    </span>
                    <p className="text-xs text-slate-500 leading-relaxed">
                      Every factual claim includes a server-validated citation link <code className="text-[10px] bg-slate-100 px-1 py-0.5 rounded">[PRODUCT:ID]</code>.
                    </p>
                  </div>

                  <div className="p-4 rounded-xl bg-white border border-slate-200/90 shadow-2xs">
                    <span className="text-xs font-bold text-indigo-700 block mb-1">
                      3. Deterministic Engine
                    </span>
                    <p className="text-xs text-slate-500 leading-relaxed">
                      Answers, clarifies, or refuses deterministically. The LLM cannot override evidence decisions.
                    </p>
                  </div>
                </div>

                {/* Suggested Example Queries */}
                <div className="w-full text-left space-y-2.5 pt-2">
                  <span className="text-xs font-bold uppercase tracking-wider text-slate-400 block text-center">
                    Try Hackathon Verification Queries
                  </span>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    {samplePrompts.map((p, idx) => (
                      <button
                        key={idx}
                        onClick={() => handleSendMessage(p.query)}
                        className="p-3 rounded-xl bg-white hover:bg-slate-50 border border-slate-200 text-left transition-all hover:border-indigo-300 shadow-2xs group flex items-center justify-between cursor-pointer"
                      >
                        <div>
                          <span className="text-[10px] font-semibold uppercase text-indigo-600 block">
                            {p.label}
                          </span>
                          <span className="text-xs font-medium text-slate-800">
                            "{p.query}"
                          </span>
                        </div>
                        <ArrowRight className="h-4 w-4 text-slate-400 group-hover:text-indigo-600 group-hover:translate-x-0.5 transition-all shrink-0 ml-2" />
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            ) : (
              <div className="flex-1 space-y-4 overflow-y-auto mb-6 pr-1">
                {messages.map((msg) => (
                  <ChatMessage
                    key={msg.id}
                    message={msg}
                    onOpenEvidence={handleOpenEvidence}
                    onSelectSuggestion={(sugg) => handleSendMessage(sugg)}
                    onReportIssue={handleOpenReportFromMessage}
                  />
                ))}
                {isLoading && (
                  <div className="flex items-center space-x-3 text-slate-500 text-xs py-3 pl-2 animate-pulse">
                    <div className="h-2 w-2 rounded-full bg-indigo-600 animate-ping" />
                    <span>Verifying facts against ground-truth catalogue...</span>
                  </div>
                )}
                <div ref={messagesEndRef} />
              </div>
            )}

            {/* Error Banner */}
            {error && (
              <div className="mb-4 p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs flex items-center justify-between animate-fade-in">
                <span>{error}</span>
                <button
                  onClick={() => setError(null)}
                  className="text-rose-500 hover:text-rose-700 cursor-pointer font-bold ml-2"
                >
                  ✕
                </button>
              </div>
            )}

            {/* Chat Input Bar */}
            <div className="sticky bottom-4 bg-white rounded-2xl border border-slate-200/90 shadow-lg p-2 flex items-center space-x-2 focus-within:ring-2 focus-within:ring-indigo-500 focus-within:border-transparent transition-all">
              <input
                type="text"
                value={inputMessage}
                onChange={(e) => setInputMessage(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    handleSendMessage();
                  }
                }}
                placeholder="Ask about product specs, prices, stock, comparisons, or policies..."
                className="flex-1 px-3 py-2 text-sm bg-transparent focus:outline-none text-slate-800 placeholder-slate-400"
                disabled={isLoading}
              />
              <button
                type="button"
                onClick={handleToggleVoiceInput}
                disabled={isLoading}
                title={isListening ? "Listening... click to stop" : "Voice search (English, Telugu, Hindi)"}
                className={`p-2.5 rounded-xl transition-all cursor-pointer shadow-xs shrink-0 ${
                  isListening
                    ? "bg-rose-500 text-white animate-pulse"
                    : "bg-slate-100 hover:bg-slate-200 text-slate-600"
                }`}
              >
                {isListening ? <MicOff className="h-4 w-4" /> : <Mic className="h-4 w-4" />}
              </button>
              <button
                onClick={() => handleSendMessage()}
                disabled={!inputMessage.trim() || isLoading}
                className="p-2.5 rounded-xl bg-indigo-600 text-white hover:bg-indigo-700 disabled:bg-slate-200 disabled:text-slate-400 disabled:cursor-not-allowed transition-all cursor-pointer shadow-xs shrink-0"
              >
                <Send className="h-4 w-4" />
              </button>
            </div>
          </div>
        )}

        {/* CUSTOMER: Product Browse View */}
        {currentView === "browse" && (
          <ProductBrowseView
            onAskInChat={(query) => {
              setCurrentView("chat");
              handleSendMessage(query);
            }}
            onReportProduct={handleOpenReportForSku}
            isDemo={Boolean(currentUser?.is_demo)}
          />
        )}

        {/* CUSTOMER: Feedback History View */}
        {currentView === "feedback" && currentUser?.role !== "OWNER" && (
          <MyFeedbackView
            currentUser={currentUser}
            onOpenNewFeedback={() => {
              setFeedbackPrefillSku(undefined);
              setFeedbackPrefillConv(undefined);
              setIsFeedbackModalOpen(true);
            }}
            onOpenLogin={() => {
              setAuthModalDefaultTab("login");
              setIsAuthModalOpen(true);
            }}
          />
        )}

        {/* CUSTOMER: Store Policies View */}
        {(currentView === "policy" || currentView === "policies") && <PolicyView />}

        {/* OWNER: Dashboard Overview */}
        {(currentView === "owner-dashboard" || currentView === "dashboard") && (
          currentUser?.role === "OWNER" ? (
            <OwnerDashboardView
              onNavigate={setCurrentView}
              onOpenEvaluation={() => setIsEvaluationOpen(true)}
              isDemo={Boolean(currentUser?.is_demo)}
            />
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center p-8 text-center space-y-3">
              <div className="p-6 rounded-2xl bg-white border border-slate-200 shadow-sm max-w-md">
                <h3 className="font-bold text-sm text-slate-800 mb-1">Store Owner Access Required</h3>
                <p className="text-xs text-slate-500 mb-4">
                  This section is restricted to authorized store owners. Please sign in with owner credentials to access store operations.
                </p>
                <button
                  onClick={() => {
                    setAuthModalDefaultTab("owner");
                    setIsAuthModalOpen(true);
                  }}
                  className="px-4 py-2 bg-purple-700 hover:bg-purple-800 text-white font-semibold text-xs rounded-xl transition-colors cursor-pointer"
                >
                  Sign In to Owner Portal
                </button>
              </div>
            </div>
          )
        )}

        {/* OWNER: Catalogue Management */}
        {currentUser?.role === "OWNER" && (currentView === "owner-catalogue" || currentView === "catalogue") && <OwnerCatalogueView isDemo={Boolean(currentUser?.is_demo)} />}

        {/* OWNER: Product Management */}
        {currentUser?.role === "OWNER" && (currentView === "owner-products" || currentView === "products") && <OwnerProductsView isDemo={Boolean(currentUser?.is_demo)} />}

        {/* OWNER: Feedback Management */}
        {currentUser?.role === "OWNER" && (currentView === "owner-feedback" || currentView === "feedback") && <OwnerFeedbackView />}

        {/* OWNER: Policy Management */}
        {currentUser?.role === "OWNER" && (currentView === "owner-policy" || currentView === "owner-policies") && <OwnerPolicyView isDemo={Boolean(currentUser?.is_demo)} />}

        {/* OWNER: Audit Trail */}
        {currentUser?.role === "OWNER" && (currentView === "owner-audit" || currentView === "audit") && <OwnerAuditView />}
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-200 bg-white py-4 text-center text-xs text-slate-400">
        TruthCart AI • Team TalentX • Talent AP Mega Hackathon 2026 • Problem Statement R3: Retail Track
      </footer>

      {/* Evidence Drawer */}
      <EvidenceDrawer
        isOpen={isEvidenceOpen}
        onClose={() => setIsEvidenceOpen(false)}
        evidence={selectedEvidence?.evidence || null}
        latencyMs={selectedEvidence?.latencyMs}
        retrievalStatus={selectedEvidence?.retrievalStatus}
        modelStatus={selectedEvidence?.modelStatus}
      />

      {/* Evaluation Modal */}
      <EvaluationModal
        isOpen={isEvaluationOpen}
        onClose={() => setIsEvaluationOpen(false)}
      />

      {/* Auth Modal */}
      <AuthModal
        isOpen={isAuthModalOpen}
        onClose={() => setIsAuthModalOpen(false)}
        defaultTab={authModalDefaultTab}
        onSuccess={(user) => {
          setCurrentUser(user);
          if (user.role === "OWNER") {
            setCurrentView("owner-dashboard");
          }
          loadAppStatus();
        }}
      />

      {/* Feedback Modal */}
      <FeedbackModal
        isOpen={isFeedbackModalOpen}
        onClose={() => setIsFeedbackModalOpen(false)}
        prefillProductId={feedbackPrefillSku}
        prefillConversationId={feedbackPrefillConv}
        onSuccess={() => {
          // If in feedback tab, reload
          if (currentView === "feedback") {
            setCurrentView("feedback");
          }
        }}
      />
    </div>
  );
}

export default App;

