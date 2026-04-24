import { Box, Text, useInput } from '@hermes/ink'
import { useEffect, useState } from 'react'

import type { GatewayClient } from '../gatewayClient.js'
import type { SessionListItem, SessionListResponse } from '../gatewayTypes.js'
import { asRpcResult, rpcErrorMessage } from '../lib/rpc.js'
import type { Theme } from '../theme.js'

const VISIBLE = 15

const age = (ts: number) => {
  const d = (Date.now() / 1000 - ts) / 86400

  if (d < 1) {
    return 'today'
  }

  if (d < 2) {
    return 'yesterday'
  }

  return `${Math.floor(d)}d ago`
}

export function SessionPicker({ gw, onCancel, onSelect, t }: SessionPickerProps) {
  const [items, setItems] = useState<SessionListItem[]>([])
  const [err, setErr] = useState('')
  const [sel, setSel] = useState(0)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    gw.request<SessionListResponse>('session.list', { limit: 20 })
      .then(raw => {
        const r = asRpcResult<SessionListResponse>(raw)

        if (!r) {
          setErr('invalid response: session.list')
          setLoading(false)

          return
        }

        setItems(r.sessions ?? [])
        setErr('')
        setLoading(false)
      })
      .catch((e: unknown) => {
        setErr(rpcErrorMessage(e))
        setLoading(false)
      })
  }, [gw])

  useInput((ch, key) => {
    if (key.escape) {
      return onCancel()
    }

    if (key.upArrow && sel > 0) {
      setSel(s => s - 1)
    }

    if (key.downArrow && sel < items.length - 1) {
      setSel(s => s + 1)
    }

    if (key.return && items[sel]) {
      onSelect(items[sel]!.id)
    }

    const n = parseInt(ch)

    if (n >= 1 && n <= Math.min(9, items.length)) {
      onSelect(items[n - 1]!.id)
    }
  })

  if (loading) {
    return <Text color={t.color.panelMuted}>loading sessions…</Text>
  }

  if (err) {
    return (
      <Box flexDirection="column">
        <Text color={t.color.error}>error: {err}</Text>
        <Text color={t.color.dim}>Esc to cancel</Text>
      </Box>
    )
  }

  if (!items.length) {
    return (
      <Box flexDirection="column">
        <Text color={t.color.dim}>no previous sessions</Text>
        <Text color={t.color.dim}>Esc to cancel</Text>
      </Box>
    )
  }

  const off = Math.max(0, Math.min(sel - Math.floor(VISIBLE / 2), items.length - VISIBLE))

  return (
    <Box flexDirection="column">
      <Box flexWrap="wrap" marginBottom={1}>
        <Text backgroundColor={t.color.chipBg} color={t.color.chipText}>
          {' '}
          sessions
          {' '}
        </Text>
        <Text color={t.color.cornsilk}> resume a previous thread</Text>
      </Box>

      {off > 0 && <Text color={t.color.dim}> ↑ {off} more</Text>}

      {items.slice(off, off + VISIBLE).map((s, vi) => {
        const i = off + vi
        const active = sel === i

        return (
          <Box
            backgroundColor={active ? t.color.completionCurrentBg : undefined}
            flexDirection="column"
            key={s.id}
            marginBottom={1}
          >
            <Box>
              <Text color={active ? t.color.label : t.color.dim}>{active ? '▸ ' : '· '}</Text>

              <Box width={30}>
                <Text color={active ? t.color.cornsilk : t.color.panelMuted}>
                  {String(i + 1).padStart(2)}. [{s.id}]
                </Text>
              </Box>

              <Text color={t.color.dim}>({s.message_count} msgs, {age(s.started_at)}, {s.source || 'tui'})</Text>
            </Box>

            <Text color={active ? t.color.cornsilk : t.color.panelMuted} wrap="truncate-end">
              {s.title || s.preview || '(untitled)'}
            </Text>
          </Box>
        )
      })}

      {off + VISIBLE < items.length && <Text color={t.color.dim}> ↓ {items.length - off - VISIBLE} more</Text>}
      <Text color={t.color.dim}>↑/↓ select · Enter resume · 1-9 quick · Esc cancel</Text>
    </Box>
  )
}

interface SessionPickerProps {
  gw: GatewayClient
  onCancel: () => void
  onSelect: (id: string) => void
  t: Theme
}
