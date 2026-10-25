import { createContext, useContext, useRef, useState } from 'react'
import { emptyContribution, type ContributionInput } from './contribution'
import type { Guide } from './guide'

export interface ContributionSession { input: ContributionInput; draft: string; referenceRevision: string }
export const ContributionSessions = createContext<Map<string, ContributionSession> | null>(null)

export function useContributionSession(guide: Guide) {
  const sessions = useContext(ContributionSessions)
  const key = JSON.stringify([guide.repo_url.replace(/\/$/, '').toLowerCase(), guide.default_branch])
  const [session, setSessionState] = useState<ContributionSession>(() => sessions?.get(key) ?? {
    input: emptyContribution(), draft: '', referenceRevision: guide.default_branch,
  })
  const current = useRef(session)
  const updateSession = (update: (value: ContributionSession) => ContributionSession) => {
    const next = update(current.current)
    current.current = next
    sessions?.set(key, next)
    setSessionState(next)
  }
  return { session, updateSession }
}
