import { useState, type ReactNode } from 'react'
import { ContributionSessions, type ContributionSession } from '../types/contributionSession'

// Tab memory only: raw diffs never enter localStorage, the backend or a model.
export function ContributionSessionProvider({ children }: { children: ReactNode }) {
  const [sessions] = useState(() => new Map<string, ContributionSession>())
  return <ContributionSessions.Provider value={sessions}>{children}</ContributionSessions.Provider>
}
