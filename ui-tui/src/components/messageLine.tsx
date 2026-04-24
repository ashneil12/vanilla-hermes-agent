import { Ansi, Box, NoSelect, Text } from '@hermes/ink'
import { memo } from 'react'

import { LONG_MSG } from '../config/limits.js'
import { userDisplay } from '../domain/messages.js'
import { ROLE } from '../domain/roles.js'
import { compactPreview, hasAnsi, isPasteBackedText, stripAnsi } from '../lib/text.js'
import type { Theme } from '../theme.js'
import type { DetailsMode, Msg } from '../types.js'

import { Md } from './markdown.js'
import { ToolTrail } from './thinking.js'

function messageCardTone(msg: Msg, t: Theme) {
  if (msg.role === 'assistant') {
    return {
      backgroundColor: t.color.panelAltBg,
      borderColor: t.color.statusBorder,
      bodyColor: t.color.cornsilk,
      label: t.brand.name,
      labelBg: t.color.chipBg,
      labelColor: t.color.chipText
    }
  }

  if (msg.role === 'user') {
    return {
      backgroundColor: t.color.panelBg,
      borderColor: t.color.amber,
      bodyColor: t.color.cornsilk,
      label: 'you',
      labelBg: t.color.chipAccentBg,
      labelColor: t.color.chipAccentText
    }
  }

  return null
}

function toolPreview(text: string, cols: number) {
  const lines = text.split('\n')
  const shown = lines.slice(0, 5).map(line => compactPreview(line, Math.max(24, cols - 20)))

  return {
    hidden: Math.max(0, lines.length - shown.length),
    shown
  }
}

export const MessageLine = memo(function MessageLine({
  cols,
  compact,
  detailsMode = 'collapsed',
  isStreaming = false,
  msg,
  t
}: MessageLineProps) {
  if (msg.kind === 'trail' && msg.tools?.length) {
    return detailsMode === 'hidden' ? null : (
      <Box flexDirection="column" marginTop={1}>
        <ToolTrail detailsMode={detailsMode} t={t} trail={msg.tools} />
      </Box>
    )
  }

  if (msg.role === 'tool') {
    const raw = hasAnsi(msg.text) ? stripAnsi(msg.text) : msg.text
    const preview = toolPreview(raw, cols)

    return (
      <Box marginLeft={3}>
        <Box
          backgroundColor={t.color.panelAltBg}
          borderColor={t.color.statusBorder}
          borderStyle="single"
          flexDirection="column"
          opaque
          paddingX={1}
          paddingY={0}
          width={Math.max(20, cols - 6)}
        >
          <Box flexWrap="wrap" marginBottom={1}>
            <Text backgroundColor={t.color.chipBg} color={t.color.chipText}>
              {' '}
              tool output
              {' '}
            </Text>
            <Text color={t.color.panelMuted}> {preview.shown.length} line{preview.shown.length === 1 ? '' : 's'}</Text>
          </Box>

          {raw.trim() ? (
            <>
              {preview.shown.map((line, index) => (
                <Text color={t.color.panelMuted} key={index} wrap="truncate-end">
                  {line || ' '}
                </Text>
              ))}

              {preview.hidden > 0 ? (
                <Text color={t.color.dim}>… {preview.hidden} more line{preview.hidden === 1 ? '' : 's'}</Text>
              ) : null}
            </>
          ) : (
            <Text color={t.color.panelMuted}>(empty tool result)</Text>
          )}
        </Box>
      </Box>
    )
  }

  const { body, glyph, prefix } = ROLE[msg.role](t)
  const cardTone = msg.kind === 'slash' ? null : messageCardTone(msg, t)
  const thinking = msg.thinking?.trim() ?? ''
  const showDetails = detailsMode !== 'hidden' && (Boolean(msg.tools?.length) || Boolean(thinking))
  const contentBody = cardTone?.bodyColor ?? body

  const content = (() => {
    if (msg.kind === 'slash') {
      return <Text color={t.color.dim}>{msg.text}</Text>
    }

    if (msg.role !== 'user' && hasAnsi(msg.text)) {
      return <Ansi>{msg.text}</Ansi>
    }

    if (msg.role === 'assistant') {
      return isStreaming ? <Text color={contentBody}>{msg.text}</Text> : <Md compact={compact} t={t} text={msg.text} />
    }

    if (msg.role === 'user' && msg.text.length > LONG_MSG && isPasteBackedText(msg.text)) {
      const [head, ...rest] = userDisplay(msg.text).split('[long message]')

      return (
        <Text color={contentBody}>
          {head}
          <Text color={t.color.dim} dimColor>
            [long message]
          </Text>
          {rest.join('')}
        </Text>
      )
    }

    return <Text {...(contentBody ? { color: contentBody } : {})}>{msg.text}</Text>
  })()

  return (
    <Box
      flexDirection="column"
      marginBottom={msg.role === 'assistant' || msg.role === 'user' ? 1 : 0}
      marginTop={msg.role === 'user' || msg.kind === 'slash' ? 1 : 0}
    >
      {showDetails && (
        <Box flexDirection="column" marginBottom={1}>
          <ToolTrail
            detailsMode={detailsMode}
            reasoning={thinking}
            reasoningTokens={msg.thinkingTokens}
            t={t}
            toolTokens={msg.toolTokens}
            trail={msg.tools}
          />
        </Box>
      )}

      <Box>
        <NoSelect flexShrink={0} fromLeftEdge width={3}>
          <Text bold={msg.role === 'user'} color={prefix}>
            {glyph}{' '}
          </Text>
        </NoSelect>

        {cardTone ? (
          <Box
            backgroundColor={cardTone.backgroundColor}
            borderColor={cardTone.borderColor}
            borderStyle="single"
            flexDirection="column"
            opaque
            paddingX={1}
            paddingY={0}
            width={Math.max(20, cols - 5)}
          >
            <Box flexWrap="wrap" marginBottom={1}>
              <Text backgroundColor={cardTone.labelBg} color={cardTone.labelColor}>
                {' '}
                {cardTone.label}
                {' '}
              </Text>
              {isStreaming ? <Text color={t.color.panelMuted}> streaming…</Text> : null}
            </Box>

            {content}
          </Box>
        ) : (
          <Box width={Math.max(20, cols - 5)}>{content}</Box>
        )}
      </Box>
    </Box>
  )
})

interface MessageLineProps {
  cols: number
  compact?: boolean
  detailsMode?: DetailsMode
  isStreaming?: boolean
  msg: Msg
  t: Theme
}
