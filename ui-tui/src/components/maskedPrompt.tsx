import { Box, Text } from '@hermes/ink'
import { useState } from 'react'

import type { Theme } from '../theme.js'

import { TextInput } from './textInput.js'

export function MaskedPrompt({ cols = 80, icon, label, onSubmit, sub, t }: MaskedPromptProps) {
  const [value, setValue] = useState('')

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
      <Box flexWrap="wrap" marginBottom={1}>
        <Text backgroundColor={t.color.chipAccentBg} color={t.color.chipAccentText}>
          {' '}
          secure input
          {' '}
        </Text>
        <Text color={t.color.cornsilk}>
          {' '}
          {icon} {label}
        </Text>
      </Box>

      {sub ? (
        <Text color={t.color.panelMuted} wrap="wrap-trim">
          {sub}
        </Text>
      ) : null}

      <Box
        backgroundColor={t.color.panelAltBg}
        borderColor={t.color.statusBorder}
        borderStyle="single"
        flexDirection="column"
        marginTop={1}
        opaque
        paddingX={1}
        paddingY={0}
      >
        <Box>
          <Text color={t.color.label}>{'> '}</Text>
          <TextInput columns={Math.max(20, cols - 12)} mask="*" onChange={setValue} onSubmit={onSubmit} value={value} />
        </Box>
      </Box>

      <Box marginTop={1}>
        <Text color={t.color.dim}>Enter submit · Ctrl+C cancel</Text>
      </Box>
    </Box>
  )
}

interface MaskedPromptProps {
  cols?: number
  icon: string
  label: string
  onSubmit: (v: string) => void
  sub?: string
  t: Theme
}
