export const DEFAULT_GUIDE_TIMEOUT = 25
export const MIN_GUIDE_TIMEOUT = 10
export const MAX_GUIDE_TIMEOUT = 120
const STORAGE_KEY = 'openguide.guide-model-timeout-seconds'

export function isGuideTimeout(value: unknown): value is number {
  return typeof value === 'number' && Number.isInteger(value) && value >= MIN_GUIDE_TIMEOUT && value <= MAX_GUIDE_TIMEOUT
}

export function guideRequestTimeoutMs(seconds: number, useLlm = true): number {
  const timeout = isGuideTimeout(seconds) ? seconds : DEFAULT_GUIDE_TIMEOUT
  // Four sequential model calls plus collection allowance. This is the
  // browser's total wait limit, distinct from each model's network timeout.
  return useLlm ? Math.max(180_000, (4 * timeout + 80) * 1000) : 180_000
}

export function loadGuideTimeout(): number {
  try {
    const value = Number(window.localStorage.getItem(STORAGE_KEY))
    return isGuideTimeout(value) ? value : DEFAULT_GUIDE_TIMEOUT
  } catch { return DEFAULT_GUIDE_TIMEOUT }
}

export function saveGuideTimeout(value: number): void {
  if (!isGuideTimeout(value)) return
  try { window.localStorage.setItem(STORAGE_KEY, String(value)) } catch { /* current page still works */ }
}
