import { Box, Text, useStdout } from '@hermes/ink'

import { artWidth, caduceus, CADUCEUS_WIDTH, logo } from '../banner.js'
import { flat } from '../lib/text.js'
import type { Theme } from '../theme.js'
import type { PanelSection, SessionInfo } from '../types.js'

function Chip({ accent = false, t, text }: { accent?: boolean; t: Theme; text: string }) {
  return (
    <Text
      backgroundColor={accent ? t.color.chipAccentBg : t.color.chipBg}
      color={accent ? t.color.chipAccentText : t.color.chipText}
    >
      {` ${text} `}
    </Text>
  )
}

export function ArtLines({ lines }: { lines: [string, string][] }) {
  return (
    <>
      {lines.map(([c, text], i) => (
        <Text color={c} key={i}>
          {text}
        </Text>
      ))}
    </>
  )
}

export function Banner({ t }: { t: Theme }) {
  const cols = useStdout().stdout?.columns ?? 80
  const logoLines = logo(t.color, t.bannerLogo || undefined)
  const showArt = Boolean(t.bannerLogo) && cols >= artWidth(logoLines)

  return (
    <Box
      backgroundColor={t.color.panelBg}
      borderColor={t.color.panelBorder}
      borderStyle="single"
      flexDirection="column"
      marginBottom={1}
      opaque
      paddingX={1}
      paddingY={0}
    >
      {showArt ? (
        <Box flexDirection="column" marginBottom={1}>
          <ArtLines lines={logoLines} />
        </Box>
      ) : null}

      <Box flexWrap="wrap">
        <Box marginRight={1}>
          <Chip accent t={t} text="Hermes TUI" />
        </Box>
        <Text bold color={t.color.cornsilk}>
          {t.brand.name}
        </Text>
        <Text color={t.color.panelMuted}> · Nous Research</Text>
      </Box>
      <Text color={t.color.dim}>{t.brand.welcome}</Text>
    </Box>
  )
}

export function SessionPanel({ info, sid, t }: SessionPanelProps) {
  const cols = useStdout().stdout?.columns ?? 100
  const heroLines = caduceus(t.color, t.bannerHero || undefined)
  const showHeroArt = cols >= 120
  const leftW = showHeroArt ? Math.min((artWidth(heroLines) || CADUCEUS_WIDTH) + 2, Math.floor(cols * 0.28)) : 24
  const wide = cols >= 96
  const sectionWide = cols >= 120
  const w = Math.max(20, wide ? cols - leftW - 10 : cols - 8)
  const lineBudget = Math.max(12, w - 2)
  const strip = (s: string) => (s.endsWith('_tools') ? s.slice(0, -6) : s)
  const toolCount = flat(info.tools).length
  const skillCount = flat(info.skills).length
  const modelLabel = info.model.split('/').pop() || info.model

  const truncLine = (pfx: string, items: string[]) => {
    let line = ''
    let shown = 0

    for (const item of [...items].sort()) {
      const next = line ? `${line}, ${item}` : item

      if (pfx.length + next.length > lineBudget) {
        return line ? `${line}, …+${items.length - shown}` : `${item}, …`
      }

      line = next
      shown++
    }

    return line
  }

  const section = (title: string, data: Record<string, string[]>, max = 8, overflowLabel = 'more…') => {
    const entries = Object.entries(data).sort()
    const shown = entries.slice(0, max)
    const overflow = entries.length - max

    return (
      <Box
        backgroundColor={t.color.panelAltBg}
        borderColor={t.color.panelBorder}
        borderStyle="single"
        flexDirection="column"
        flexGrow={1}
        marginTop={1}
        opaque
        paddingX={1}
        paddingY={0}
      >
        <Text bold color={t.color.amber}>
          {title}
        </Text>

        {shown.length ? (
          shown.map(([k, vs]) => (
            <Text color={t.color.cornsilk} key={k} wrap="truncate">
              <Text color={t.color.dim}>{strip(k)}: </Text>
              {truncLine(strip(k) + ': ', vs)}
            </Text>
          ))
        ) : (
          <Text color={t.color.dim}>none detected</Text>
        )}

        {overflow > 0 && <Text color={t.color.dim}>+{overflow} {overflowLabel}</Text>}
      </Box>
    )
  }

  return (
    <Box
      backgroundColor={t.color.panelBg}
      borderColor={t.color.panelBorder}
      borderStyle="single"
      flexDirection="column"
      marginBottom={1}
      opaque
      paddingX={1}
      paddingY={0}
    >
      <Box flexWrap="wrap" marginBottom={1}>
        <Box marginRight={1}>
          <Chip accent t={t} text="Hermes session" />
        </Box>
        <Box marginRight={1}>
          <Chip t={t} text={modelLabel} />
        </Box>
        {info.version ? (
          <Box marginRight={1}>
            <Chip t={t} text={`v${info.version}`} />
          </Box>
        ) : null}
        {sid ? (
          <Box marginRight={1}>
            <Chip t={t} text={`session ${sid}`} />
          </Box>
        ) : null}
      </Box>

      <Text color={t.color.panelMuted} wrap="truncate-end">
        {info.cwd || process.cwd()}
        {info.release_date ? ` · ${info.release_date}` : ''}
      </Text>

      <Box flexDirection={wide ? 'row' : 'column'} marginTop={1}>
        <Box flexDirection="column" marginBottom={wide ? 0 : 1} marginRight={wide ? 2 : 0} width={wide ? leftW : undefined}>
          {showHeroArt ? (
            <Box
              backgroundColor={t.color.panelAltBg}
              borderColor={t.color.sessionBorder}
              borderStyle="single"
              flexDirection="column"
              opaque
              paddingX={1}
              paddingY={0}
            >
              <ArtLines lines={heroLines} />
            </Box>
          ) : (
            <Box
              backgroundColor={t.color.panelAltBg}
              borderColor={t.color.sessionBorder}
              borderStyle="single"
              flexDirection="column"
              opaque
              paddingX={1}
              paddingY={0}
            >
              <Text bold color={t.color.gold}>
                {t.brand.icon} Nous Hermes
              </Text>
              <Text color={t.color.dim}>Dedicated terminal workspace</Text>
              <Text color={t.color.cornsilk}>{toolCount} tools ready</Text>
              <Text color={t.color.cornsilk}>{skillCount} skills ready</Text>
            </Box>
          )}
        </Box>

        <Box flexDirection={sectionWide ? 'row' : 'column'} flexGrow={1} width={w}>
          <Box flexDirection="column" flexGrow={1} marginRight={sectionWide ? 1 : 0}>
            {section('Available tools', info.tools, 7, 'more toolsets…')}
          </Box>
          <Box flexDirection="column" flexGrow={1} marginLeft={sectionWide ? 1 : 0}>
            {section('Available skills', info.skills, 7, 'more skills…')}
          </Box>
        </Box>
      </Box>

      <Box flexWrap="wrap" marginTop={1}>
        <Text color={t.color.cornsilk}>
          {toolCount} tools · {skillCount} skills · <Text color={t.color.dim}>/help for commands</Text>
        </Text>
      </Box>

      {typeof info.update_behind === 'number' && info.update_behind > 0 && (
        <Text bold color="yellow">
          ! {info.update_behind} {info.update_behind === 1 ? 'commit' : 'commits'} behind
          <Text bold={false} color="yellow" dimColor>
            {' '}
            · run{' '}
          </Text>
          <Text bold color="yellow">
            {info.update_command || 'hermes update'}
          </Text>
        </Text>
      )}
    </Box>
  )
}

export function Panel({ sections, t, title }: PanelProps) {
  return (
    <Box
      backgroundColor={t.color.panelBg}
      borderColor={t.color.panelBorder}
      borderStyle="single"
      flexDirection="column"
      opaque
      paddingX={1}
      paddingY={0}
    >
      <Box justifyContent="center" marginBottom={1}>
        <Text bold color={t.color.gold}>
          {title}
        </Text>
      </Box>

      {sections.map((sec, si) => (
        <Box flexDirection="column" key={si} marginTop={si > 0 ? 1 : 0}>
          {sec.title && (
            <Text bold color={t.color.amber}>
              {sec.title}
            </Text>
          )}

          {sec.rows?.map(([k, v], ri) => (
            <Text key={ri} wrap="truncate">
              <Text color={t.color.dim}>{k.padEnd(20)}</Text>
              <Text color={t.color.cornsilk}>{v}</Text>
            </Text>
          ))}

          {sec.items?.map((item, ii) => (
            <Text color={t.color.cornsilk} key={ii} wrap="truncate">
              {item}
            </Text>
          ))}

          {sec.text && <Text color={t.color.dim}>{sec.text}</Text>}
        </Box>
      ))}
    </Box>
  )
}

interface PanelProps {
  sections: PanelSection[]
  t: Theme
  title: string
}

interface SessionPanelProps {
  info: SessionInfo
  sid?: string | null
  t: Theme
}
