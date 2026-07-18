// Liveness signal for the Hivra dashboard, which embeds this app in an iframe.
//
// The dashboard cannot tell a working chat from a broken one on its own: the
// iframe's DOM `load` event fires for ANY completed document — an HTTP error
// page, a CSP-blocked frame, a blank shell — and no `error` event fires for
// any of those. So a box that served a 200 shell and then rendered nothing
// looked identical to a healthy one, and was recorded as a success.
//
// This is the other half of that contract: once the gateway boot has actually
// completed (gateway connected, config loaded, sessions loaded) we tell the
// embedder the chat is alive. The dashboard arms a watchdog on document load
// and clears it when this arrives.
//
// The dashboard does NOT depend on this to avoid false alarms — on timeout it
// falls back to a server-side gateway probe, so boxes running an image older
// than this emit are still judged correctly. This just makes the healthy path
// fast and free.

const READY_MESSAGE_TYPE = 'HERMES_WEBUI_READY'

// Emit once per document. Boot can complete again on reconnect, and a second
// signal would be noise — the embedder only needs to learn "alive" once.
let alreadySignalled = false

export function resetEmbedReadySignalForTests(): void {
  alreadySignalled = false
}

export function signalEmbedReady(): void {
  if (alreadySignalled) {
    return
  }

  try {
    // Not embedded (Electron, or a directly-opened browser tab): nobody to
    // tell. `window.parent === window` for a top-level document.
    if (typeof window === 'undefined' || window.parent === window) {
      return
    }

    // targetOrigin '*' is deliberate. The box does not know which dashboard
    // origin embedded it (hermesos.cloud, hivra.cloud, canary, …), and
    // hardcoding that list here would duplicate the per-box Caddy
    // frame-ancestors allowlist and rot out of sync with it. This is safe
    // because the payload carries NO data — it is a bare liveness ping, and a
    // type name is not a secret. The security boundary lives on the receiving
    // side: the dashboard validates both event.origin and event.source before
    // trusting it, so a hostile embedder learns nothing and cannot forge a
    // confirmation for someone else's frame.
    window.parent.postMessage({ type: READY_MESSAGE_TYPE }, '*')
    alreadySignalled = true
  } catch {
    // Telling the embedder we are alive must never be able to break the boot
    // path that just succeeded.
  }
}
