export interface ThemeColors {
  surfaceBg: string
  panelBg: string
  panelAltBg: string
  panelBorder: string
  panelMuted: string
  chipBg: string
  chipBorder: string
  chipText: string
  chipAccentBg: string
  chipAccentBorder: string
  chipAccentText: string

  gold: string
  amber: string
  bronze: string
  cornsilk: string
  dim: string
  completionBg: string
  completionCurrentBg: string

  label: string
  ok: string
  error: string
  warn: string

  prompt: string
  sessionLabel: string
  sessionBorder: string

  statusBg: string
  statusFg: string
  statusBorder: string
  statusGood: string
  statusWarn: string
  statusBad: string
  statusCritical: string
  selectionBg: string

  diffAdded: string
  diffRemoved: string
  diffAddedWord: string
  diffRemovedWord: string

  shellDollar: string
}

export interface ThemeBrand {
  name: string
  icon: string
  prompt: string
  welcome: string
  goodbye: string
  tool: string
  helpHeader: string
}

export interface Theme {
  color: ThemeColors
  brand: ThemeBrand
  bannerLogo: string
  bannerHero: string
}

// ── Color math ───────────────────────────────────────────────────────

function parseHex(h: string): [number, number, number] | null {
  const m = /^#?([0-9a-f]{6})$/i.exec(h)

  if (!m) {
    return null
  }

  const n = parseInt(m[1]!, 16)

  return [(n >> 16) & 0xff, (n >> 8) & 0xff, n & 0xff]
}

function mix(a: string, b: string, t: number) {
  const pa = parseHex(a)
  const pb = parseHex(b)

  if (!pa || !pb) {
    return a
  }

  const lerp = (i: 0 | 1 | 2) => Math.round(pa[i] + (pb[i] - pa[i]) * t)

  return '#' + ((1 << 24) | (lerp(0) << 16) | (lerp(1) << 8) | lerp(2)).toString(16).slice(1)
}

// ── Defaults ─────────────────────────────────────────────────────────

export const DEFAULT_THEME: Theme = {
  color: {
    surfaceBg: '#0b0d14',
    panelBg: '#11141d',
    panelAltBg: '#171b25',
    panelBorder: '#4a3418',
    panelMuted: '#9b8b74',
    chipBg: '#171b25',
    chipBorder: '#3f4a64',
    chipText: '#ddd5c7',
    chipAccentBg: '#3a2b13',
    chipAccentBorder: '#73521b',
    chipAccentText: '#f2de9a',

    gold: '#f0d98a',
    amber: '#d4af37',
    bronze: '#c68a43',
    cornsilk: '#eee5d6',
    dim: '#9b8b74',
    completionBg: '#0f1118',
    completionCurrentBg: '#1b2434',

    label: '#d4af37',
    ok: '#4caf50',
    error: '#ef5350',
    warn: '#ffa726',

    prompt: '#eee5d6',
    sessionLabel: '#c68a43',
    sessionBorder: '#d4af37',

    statusBg: '#0f1118',
    statusFg: '#eee5d6',
    statusBorder: '#263047',
    statusGood: '#6ec7b0',
    statusWarn: '#f2de9a',
    statusBad: '#f59e0b',
    statusCritical: '#FF6B6B',
    selectionBg: '#2b3348',

    diffAdded: 'rgb(220,255,220)',
    diffRemoved: 'rgb(255,220,220)',
    diffAddedWord: 'rgb(36,138,61)',
    diffRemovedWord: 'rgb(207,34,46)',
    shellDollar: '#7dd3fc'
  },

  brand: {
    name: 'Hermes Agent',
    icon: '⚕',
    prompt: '❯',
    welcome: 'Type your message or /help for commands.',
    goodbye: 'Goodbye! ⚕',
    tool: '┊',
    helpHeader: '(^_^)? Commands'
  },

  bannerLogo: '',
  bannerHero: ''
}

// ── Skin → Theme ─────────────────────────────────────────────────────

export function fromSkin(
  colors: Record<string, string>,
  branding: Record<string, string>,
  bannerLogo = '',
  bannerHero = '',
  toolPrefix = '',
  helpHeader = ''
): Theme {
  const d = DEFAULT_THEME
  const c = (k: string) => colors[k]

  const amber = c('ui_accent') ?? c('banner_accent') ?? d.color.amber
  const accent = c('banner_accent') ?? c('banner_title') ?? d.color.amber
  const dim = c('banner_dim') ?? d.color.dim
  const panelBg = c('ui_panel_bg') ?? d.color.panelBg
  const panelAltBg = c('ui_panel_alt_bg') ?? d.color.panelAltBg
  const hasAccentOverride = Boolean(c('ui_accent') ?? c('banner_accent'))
  const hasBannerDimOverride = Boolean(c('banner_dim'))
  const hasPanelBgOverride = Boolean(c('ui_panel_bg'))
  const hasPanelAltBgOverride = Boolean(c('ui_panel_alt_bg'))
  const hasCompletionAccentOverride = Boolean(c('ui_panel_bg') ?? c('banner_accent') ?? c('banner_title'))

  return {
    color: {
      surfaceBg: c('ui_surface_bg') ?? d.color.surfaceBg,
      panelBg,
      panelAltBg,
      panelBorder: c('ui_panel_border') ?? c('banner_border') ?? d.color.panelBorder,
      panelMuted: c('ui_panel_muted') ?? d.color.panelMuted,
      chipBg: c('ui_chip_bg') ?? (hasPanelAltBgOverride ? mix(panelAltBg, '#ffffff', 0.08) : d.color.chipBg),
      chipBorder: c('ui_chip_border') ?? (hasPanelAltBgOverride ? mix(panelAltBg, '#8aa0c8', 0.28) : d.color.chipBorder),
      chipText: c('ui_chip_fg') ?? c('banner_text') ?? d.color.chipText,
      chipAccentBg: c('ui_chip_accent_bg') ?? (hasAccentOverride ? mix(amber, '#000000', 0.7) : d.color.chipAccentBg),
      chipAccentBorder:
        c('ui_chip_accent_border') ?? (hasAccentOverride ? mix(amber, '#000000', 0.45) : d.color.chipAccentBorder),
      chipAccentText: c('ui_chip_accent_fg') ?? d.color.chipAccentText,

      gold: c('banner_title') ?? d.color.gold,
      amber,
      bronze: c('banner_border') ?? d.color.bronze,
      cornsilk: c('banner_text') ?? d.color.cornsilk,
      dim,
      completionBg: c('completion_menu_bg') ?? d.color.completionBg,
      completionCurrentBg:
        c('completion_menu_current_bg') ?? (hasCompletionAccentOverride ? mix(panelBg, accent, 0.25) : d.color.completionCurrentBg),

      label: c('ui_label') ?? d.color.label,
      ok: c('ui_ok') ?? d.color.ok,
      error: c('ui_error') ?? d.color.error,
      warn: c('ui_warn') ?? d.color.warn,

      prompt: c('prompt') ?? c('banner_text') ?? d.color.prompt,
      sessionLabel: c('session_label') ?? (hasBannerDimOverride ? dim : d.color.sessionLabel),
      sessionBorder: c('session_border') ?? (hasBannerDimOverride ? dim : d.color.sessionBorder),

      statusBg: c('ui_status_bg') ?? d.color.statusBg,
      statusFg: c('ui_status_fg') ?? d.color.statusFg,
      statusBorder: c('ui_status_border') ?? d.color.statusBorder,
      statusGood: c('ui_ok') ?? d.color.statusGood,
      statusWarn: c('ui_warn') ?? d.color.statusWarn,
      statusBad: d.color.statusBad,
      statusCritical: d.color.statusCritical,
      selectionBg: c('selection_bg') ?? d.color.selectionBg,

      diffAdded: d.color.diffAdded,
      diffRemoved: d.color.diffRemoved,
      diffAddedWord: d.color.diffAddedWord,
      diffRemovedWord: d.color.diffRemovedWord,
      shellDollar: c('shell_dollar') ?? d.color.shellDollar
    },

    brand: {
      name: branding.agent_name ?? d.brand.name,
      icon: d.brand.icon,
      prompt: branding.prompt_symbol ?? d.brand.prompt,
      welcome: branding.welcome ?? d.brand.welcome,
      goodbye: branding.goodbye ?? d.brand.goodbye,
      tool: toolPrefix || d.brand.tool,
      helpHeader: branding.help_header ?? (helpHeader || d.brand.helpHeader)
    },

    bannerLogo,
    bannerHero
  }
}
