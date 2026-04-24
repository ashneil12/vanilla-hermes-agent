import { Box, Text, useInput } from '@hermes/ink'
import { type ReactNode, useState } from 'react'

import type { Theme } from '../theme.js'
import type { ApprovalReq, ClarifyReq } from '../types.js'

import { TextInput } from './textInput.js'

const OPTS = ['once', 'session', 'always', 'deny'] as const
const LABELS = { always: 'Always allow', deny: 'Deny', once: 'Allow once', session: 'Allow this session' } as const

function PromptShell({
  children,
  footer,
  subtitle,
  t,
  title,
  tone = 'accent'
}: {
  children: ReactNode
  footer?: string
  subtitle?: string
  t: Theme
  title: string
  tone?: 'accent' | 'warn'
}) {
  const borderColor = tone === 'warn' ? t.color.warn : t.color.panelBorder
  const chipBg = tone === 'warn' ? t.color.chipAccentBg : t.color.chipBg
  const chipText = tone === 'warn' ? t.color.chipAccentText : t.color.chipText

  return (
    <Box
      backgroundColor={t.color.panelBg}
      borderColor={borderColor}
      borderStyle="single"
      flexDirection="column"
      opaque
      paddingX={1}
      paddingY={0}
    >
      <Box flexWrap="wrap" marginBottom={1}>
        <Text backgroundColor={chipBg} color={chipText}>
          {' '}
          {title}
          {' '}
        </Text>
        {subtitle ? <Text color={t.color.cornsilk}> {subtitle}</Text> : null}
      </Box>

      {children}

      {footer ? (
        <Box marginTop={1}>
          <Text color={t.color.dim}>{footer}</Text>
        </Box>
      ) : null}
    </Box>
  )
}

function PromptOption({
  active,
  index,
  label,
  t
}: {
  active: boolean
  index: number
  label: string
  t: Theme
}) {
  return (
    <Box backgroundColor={active ? t.color.completionCurrentBg : undefined} flexDirection="row">
      <Text color={active ? t.color.amber : t.color.dim}>{active ? '▸ ' : '· '}</Text>
      <Text color={active ? t.color.cornsilk : t.color.panelMuted}>
        {index}. {label}
      </Text>
    </Box>
  )
}

export function ApprovalPrompt({ onChoice, req, t }: ApprovalPromptProps) {
  const [sel, setSel] = useState(0)

  useInput((ch, key) => {
    if (key.upArrow && sel > 0) {
      setSel(s => s - 1)
    }

    if (key.downArrow && sel < OPTS.length - 1) {
      setSel(s => s + 1)
    }

    const n = parseInt(ch, 10)

    if (n >= 1 && n <= OPTS.length) {
      onChoice(OPTS[n - 1]!)

      return
    }

    if (key.return) {
      onChoice(OPTS[sel]!)
    }
  })

  return (
    <PromptShell
      footer="↑/↓ select · Enter confirm · 1-4 quick pick · Ctrl+C deny"
      subtitle={req.description}
      t={t}
      title="approval"
      tone="warn"
    >
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
        <Text color={t.color.cornsilk} wrap="wrap-trim">
          {req.command}
        </Text>
      </Box>

      {OPTS.map((o, i) => (
        <PromptOption active={sel === i} index={i + 1} key={o} label={LABELS[o]} t={t} />
      ))}
    </PromptShell>
  )
}

export function ClarifyPrompt({ cols = 80, onAnswer, onCancel, req, t }: ClarifyPromptProps) {
  const [sel, setSel] = useState(0)
  const [custom, setCustom] = useState('')
  const [typing, setTyping] = useState(false)
  const choices = req.choices ?? []

  useInput((ch, key) => {
    if (key.escape) {
      typing && choices.length ? setTyping(false) : onCancel()

      return
    }

    if (typing || !choices.length) {
      return
    }

    if (key.upArrow && sel > 0) {
      setSel(s => s - 1)
    }

    if (key.downArrow && sel < choices.length) {
      setSel(s => s + 1)
    }

    if (key.return) {
      sel === choices.length ? setTyping(true) : choices[sel] && onAnswer(choices[sel]!)
    }

    const n = parseInt(ch)

    if (n >= 1 && n <= choices.length) {
      onAnswer(choices[n - 1]!)
    }
  })

  if (typing || !choices.length) {
    return (
      <PromptShell
        footer={`Enter send · Esc ${choices.length ? 'back' : 'cancel'} · Ctrl+C cancel`}
        subtitle={req.question}
        t={t}
        title="question"
      >
        <Box
          backgroundColor={t.color.panelAltBg}
          borderColor={t.color.statusBorder}
          borderStyle="single"
          flexDirection="column"
          opaque
          paddingX={1}
          paddingY={0}
        >
          <Box>
            <Text color={t.color.label}>{'> '}</Text>
            <TextInput columns={Math.max(20, cols - 12)} onChange={setCustom} onSubmit={onAnswer} value={custom} />
          </Box>
        </Box>
      </PromptShell>
    )
  }

  return (
    <PromptShell
      footer={`↑/↓ select · Enter confirm · 1-${choices.length} quick pick · Esc/Ctrl+C cancel`}
      subtitle={req.question}
      t={t}
      title="question"
    >
      {[...choices, 'Other (type your answer)'].map((c, i) => (
        <PromptOption active={sel === i} index={i + 1} key={i} label={c} t={t} />
      ))}
    </PromptShell>
  )
}

interface ApprovalPromptProps {
  onChoice: (s: string) => void
  req: ApprovalReq
  t: Theme
}

interface ClarifyPromptProps {
  cols?: number
  onAnswer: (s: string) => void
  onCancel: () => void
  req: ClarifyReq
  t: Theme
}
