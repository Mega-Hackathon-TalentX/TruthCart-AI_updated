/**
 * Environment configuration for TruthCart AI Demo Mode.
 *
 * Demo mode is strictly disabled by default.
 * It is enabled only when explicitly configured via the environment variable:
 * - VITE_TRUTHCART_DEMO_MODE="true"
 * (or backwards-compatible VITE_ENABLE_DEMO_SHORTCUTS="true")
 *
 * It is NEVER enabled merely by running in development mode (DEV) or by default in production.
 */
export const isDemoModeEnabled = (): boolean => {
  return (
    import.meta.env.VITE_TRUTHCART_DEMO_MODE === "true" ||
    import.meta.env.VITE_ENABLE_DEMO_SHORTCUTS === "true"
  );
};
