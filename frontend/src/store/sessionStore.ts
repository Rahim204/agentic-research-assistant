import { create } from "zustand";
import type { Session, SessionResults } from "../services/api";

interface SessionStore {
  currentSession: Session | null;
  results: SessionResults | null;
  setSession: (s: Session) => void;
  setResults: (r: SessionResults) => void;
  reset: () => void;
}

export const useSessionStore = create<SessionStore>((set) => ({
  currentSession: null,
  results: null,
  setSession: (s) => set({ currentSession: s }),
  setResults: (r) => set({ results: r }),
  reset: () => set({ currentSession: null, results: null }),
}));
