import { afterEach, describe, expect, it } from 'vitest'

import { readInitialMode, resolveSkin } from './context'

const originalParent = window.parent

function setParent(value: Window | object) {
  Object.defineProperty(window, 'parent', {
    configurable: true,
    value
  })
}

describe('desktop theme boot mode', () => {
  afterEach(() => {
    window.history.replaceState(null, '', '/')
    window.localStorage.clear()
    setParent(originalParent)
  })

  it('uses the dashboard iframe theme hint before persisted desktop mode', () => {
    setParent({})
    window.history.replaceState(null, '', '/?theme=dark')
    window.localStorage.setItem('hermes-desktop-mode-v1', 'light')

    expect(readInitialMode()).toBe('dark')
  })

  it('normalizes dashboard light theme aliases', () => {
    setParent({})
    window.history.replaceState(null, '', '/?theme=hermesos-light')
    window.localStorage.setItem('hermes-desktop-mode-v1', 'dark')

    expect(readInitialMode()).toBe('light')
  })

  it('falls back to persisted desktop mode outside the dashboard iframe', () => {
    setParent(window)
    window.history.replaceState(null, '', '/?theme=dark')
    window.localStorage.setItem('hermes-desktop-mode-v1', 'system')

    expect(readInitialMode()).toBe('system')
  })

  it('keeps production mode-aware default skins until the user chooses one', () => {
    expect(resolveSkin(null, 'light')).toBe('nous')
    expect(resolveSkin(null, 'dark')).toBe('mono')
    expect(resolveSkin('slate', 'dark')).toBe('slate')
  })
})
