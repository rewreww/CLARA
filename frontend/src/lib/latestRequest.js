// Ensures responses from an older patient/request cannot update the current view.
export function createLatestRequestGuard() {
  let current = null

  return {
    begin() {
      if (current) current.abort()
      const controller = new AbortController()
      current = controller
      return {
        signal: controller.signal,
        isCurrent: () => current === controller && !controller.signal.aborted,
      }
    },
    invalidate() {
      if (current) current.abort()
      current = null
    },
  }
}
