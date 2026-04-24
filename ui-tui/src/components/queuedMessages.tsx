import { Box, Text } from '@hermes/ink'

import { compactPreview } from '../lib/text.js'
import type { Theme } from '../theme.js'

export const QUEUE_WINDOW = 3

export function getQueueWindow(queueLen: number, queueEditIdx: number | null) {
  const start =
    queueEditIdx === null ? 0 : Math.max(0, Math.min(queueEditIdx - 1, Math.max(0, queueLen - QUEUE_WINDOW)))

  const end = Math.min(queueLen, start + QUEUE_WINDOW)

  return { end, showLead: start > 0, showTail: end < queueLen, start }
}

export function QueuedMessages({ cols, queueEditIdx, queued, t }: QueuedMessagesProps) {
  if (!queued.length) {
    return null
  }

  const q = getQueueWindow(queued.length, queueEditIdx)

  return (
    <Box
      backgroundColor={t.color.panelAltBg}
      borderColor={t.color.statusBorder}
      borderStyle="single"
      flexDirection="column"
      marginBottom={1}
      opaque
      paddingX={1}
      paddingY={0}
    >
      <Box flexWrap="wrap" marginBottom={1}>
        <Text backgroundColor={t.color.chipBg} color={t.color.chipText}>
          {' '}
          queued
          {' '}
        </Text>
        <Text color={t.color.panelMuted}> {queued.length} pending</Text>
        {queueEditIdx !== null ? <Text color={t.color.amber}> · editing {queueEditIdx + 1}</Text> : null}
      </Box>

      {q.showLead && (
        <Text color={t.color.dim} dimColor>
          … earlier queued messages
        </Text>
      )}

      {queued.slice(q.start, q.end).map((item, i) => {
        const idx = q.start + i
        const active = queueEditIdx === idx

        return (
          <Text
            backgroundColor={active ? t.color.completionCurrentBg : undefined}
            color={active ? t.color.cornsilk : t.color.panelMuted}
            key={`${idx}-${item.slice(0, 16)}`}
            wrap="truncate-end"
          >
            <Text color={active ? t.color.amber : t.color.dim}>{active ? '▸' : '·'} </Text>
            <Text color={active ? t.color.amber : t.color.dim}>{idx + 1}.</Text>{' '}
            {compactPreview(item, Math.max(16, cols - 18))}
          </Text>
        )
      })}

      {q.showTail && (
        <Text color={t.color.dim} dimColor>
          …and {queued.length - q.end} more queued
        </Text>
      )}
    </Box>
  )
}

interface QueuedMessagesProps {
  cols: number
  queueEditIdx: number | null
  queued: string[]
  t: Theme
}
