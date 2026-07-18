import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { resetEmbedReadySignalForTests, signalEmbedReady } from './embed-ready-signal'

describe('embed ready signal', () => {
  const realParent = window.parent

  function setParent(parent: unknown) {
    Object.defineProperty(window, 'parent', { configurable: true, value: parent })
  }

  beforeEach(() => {
    resetEmbedReadySignalForTests()
  })

  afterEach(() => {
    Object.defineProperty(window, 'parent', { configurable: true, value: realParent })
    vi.restoreAllMocks()
  })

  it('tells an embedding dashboard the chat is alive', () => {
    const postMessage = vi.fn()
    setParent({ postMessage })

    signalEmbedReady()

    expect(postMessage).toHaveBeenCalledWith({ type: 'HERMES_WEBUI_READY' }, '*')
  })

  it('stays silent when not embedded', () => {
    // Top-level document (Electron, or a directly-opened tab): window.parent
    // IS window, and there is nobody to tell.
    const postMessage = vi.fn()
    setParent(window)
    window.postMessage = postMessage

    signalEmbedReady()

    expect(postMessage).not.toHaveBeenCalled()
  })

  it('signals at most once per document', () => {
    // Boot can complete again on reconnect; the embedder only needs to learn
    // "alive" once, and a repeat would be pure noise.
    const postMessage = vi.fn()
    setParent({ postMessage })

    signalEmbedReady()
    signalEmbedReady()
    signalEmbedReady()

    expect(postMessage).toHaveBeenCalledTimes(1)
  })

  it('never lets a postMessage failure break the boot path it runs on', () => {
    setParent({
      postMessage: () => {
        throw new Error('embedder went away')
      }
    })

    expect(() => signalEmbedReady()).not.toThrow()
  })

  it('carries no data beyond the type — it is a bare liveness ping', () => {
    // targetOrigin is '*', so the payload must never be allowed to grow
    // anything sensitive. Lock the shape.
    const postMessage = vi.fn()
    setParent({ postMessage })

    signalEmbedReady()

    const [payload] = postMessage.mock.calls[0]
    expect(Object.keys(payload)).toEqual(['type'])
  })
})
