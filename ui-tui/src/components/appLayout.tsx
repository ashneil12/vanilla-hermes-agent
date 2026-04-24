import { AlternateScreen, Box, NoSelect, ScrollBox, Text } from '@hermes/ink'
import { useStore } from '@nanostores/react'
import { memo } from 'react'

import type { AppLayoutProgressProps, AppLayoutProps } from '../app/interfaces.js'
import { $isBlocked } from '../app/overlayStore.js'
import { $uiState } from '../app/uiStore.js'
import { PLACEHOLDER } from '../content/placeholders.js'
import type { Theme } from '../theme.js'
import type { DetailsMode } from '../types.js'

import { GoodVibesHeart, StatusRule, StickyPromptTracker, TranscriptScrollbar } from './appChrome.js'
import { FloatingOverlays, PromptZone } from './appOverlays.js'
import { Banner, Panel, SessionPanel } from './branding.js'
import { MessageLine } from './messageLine.js'
import { QueuedMessages } from './queuedMessages.js'
import { TextInput } from './textInput.js'
import { ToolTrail } from './thinking.js'

const StreamingAssistant = memo(function StreamingAssistant({
  busy,
  cols,
  compact,
  detailsMode,
  progress,
  t
}: StreamingAssistantProps) {
  if (!progress.showProgressArea && !progress.showStreamingArea) {
    return null
  }

  return (
    <>
      {progress.streamSegments.map((msg, i) => (
        <MessageLine cols={cols} compact={compact} detailsMode={detailsMode} key={`seg:${i}`} msg={msg} t={t} />
      ))}

      {progress.showProgressArea && (
        <Box flexDirection="column" marginBottom={progress.showStreamingArea ? 1 : 0}>
          <ToolTrail
            activity={progress.activity}
            busy={busy}
            detailsMode={detailsMode}
            outcome={progress.outcome}
            reasoning={progress.reasoning}
            reasoningActive={progress.reasoningActive}
            reasoningStreaming={progress.reasoningStreaming}
            reasoningTokens={progress.reasoningTokens}
            subagents={progress.subagents}
            t={t}
            tools={progress.tools}
            toolTokens={progress.toolTokens}
            trail={progress.turnTrail}
          />
        </Box>
      )}

      {progress.showStreamingArea && (
        <MessageLine
          cols={cols}
          compact={compact}
          detailsMode={detailsMode}
          isStreaming
          msg={{
            role: 'assistant',
            text: progress.streaming,
            ...(progress.streamPendingTools.length && { tools: progress.streamPendingTools })
          }}
          t={t}
        />
      )}

      {!progress.showStreamingArea && !!progress.streamPendingTools.length && (
        <MessageLine
          cols={cols}
          compact={compact}
          detailsMode={detailsMode}
          msg={{ kind: 'trail', role: 'system', text: '', tools: progress.streamPendingTools }}
          t={t}
        />
      )}
    </>
  )
})

const TranscriptPane = memo(function TranscriptPane({
  cols,
  progress,
  setStickyPrompt,
  transcript
}: {
  cols: number
  progress: AppLayoutProps['progress']
  setStickyPrompt: (value: string) => void
  transcript: AppLayoutProps['transcript']
}) {
  const ui = useStore($uiState)

  return (
    <>
      <ScrollBox flexDirection="column" flexGrow={1} flexShrink={1} ref={transcript.scrollRef} stickyScroll>
        <Box flexDirection="column" paddingX={1}>
          {transcript.virtualHistory.topSpacer > 0 ? <Box height={transcript.virtualHistory.topSpacer} /> : null}

          {transcript.virtualRows.slice(transcript.virtualHistory.start, transcript.virtualHistory.end).map(row => (
            <Box flexDirection="column" key={row.key} ref={transcript.virtualHistory.measureRef(row.key)}>
              {row.msg.kind === 'intro' ? (
                <Box flexDirection="column" paddingTop={1}>
                  <Banner t={ui.theme} />

                  {row.msg.info?.version && <SessionPanel info={row.msg.info} sid={ui.sid} t={ui.theme} />}
                </Box>
              ) : row.msg.kind === 'panel' && row.msg.panelData ? (
                <Panel sections={row.msg.panelData.sections} t={ui.theme} title={row.msg.panelData.title} />
              ) : (
                <MessageLine
                  cols={cols}
                  compact={ui.compact}
                  detailsMode={ui.detailsMode}
                  msg={row.msg}
                  t={ui.theme}
                />
              )}
            </Box>
          ))}

          {transcript.virtualHistory.bottomSpacer > 0 ? <Box height={transcript.virtualHistory.bottomSpacer} /> : null}

          <StreamingAssistant
            busy={ui.busy}
            cols={cols}
            compact={ui.compact}
            detailsMode={ui.detailsMode}
            progress={progress}
            t={ui.theme}
          />
        </Box>
      </ScrollBox>

      <NoSelect flexShrink={0} marginLeft={1}>
        <TranscriptScrollbar scrollRef={transcript.scrollRef} t={ui.theme} />
      </NoSelect>

      <StickyPromptTracker
        messages={transcript.historyItems}
        offsets={transcript.virtualHistory.offsets}
        onChange={setStickyPrompt}
        scrollRef={transcript.scrollRef}
      />
    </>
  )
})

const ComposerPane = memo(function ComposerPane({
  actions,
  composer,
  status
}: Pick<AppLayoutProps, 'actions' | 'composer' | 'status'>) {
  const ui = useStore($uiState)
  const isBlocked = useStore($isBlocked)
  const sh = (composer.inputBuf[0] ?? composer.input).startsWith('!')
  const promptWidth = sh ? 4 : 5
  const inputCols = Math.max(20, composer.cols - 18)

  return (
    <NoSelect flexDirection="column" flexShrink={0} fromLeftEdge paddingBottom={1} paddingX={1}>
      <QueuedMessages
        cols={composer.cols}
        queued={composer.queuedDisplay}
        queueEditIdx={composer.queueEditIdx}
        t={ui.theme}
      />

      <Box flexDirection="column" position="relative">
        {ui.statusBar && (
          <StatusRule
            bgCount={ui.bgTasks.size}
            busy={ui.busy}
            cols={composer.cols}
            cwdLabel={status.cwdLabel}
            model={ui.info?.model?.split('/').pop() ?? ''}
            sessionStartedAt={status.sessionStartedAt}
            status={ui.status}
            statusColor={status.statusColor}
            t={ui.theme}
            usage={ui.usage}
            voiceLabel={status.voiceLabel}
          />
        )}

        <FloatingOverlays
          cols={composer.cols}
          compIdx={composer.compIdx}
          completions={composer.completions}
          onModelSelect={actions.onModelSelect}
          onPickerSelect={actions.resumeById}
          pagerPageSize={composer.pagerPageSize}
        />
      </Box>

      {!isBlocked && (
        <Box
          backgroundColor={ui.theme.color.panelBg}
          borderColor={ui.theme.color.panelBorder}
          borderStyle="single"
          flexDirection="column"
          marginBottom={1}
          opaque
          paddingX={1}
          paddingY={0}
        >
          <Box flexWrap="wrap" marginBottom={1}>
            <Text backgroundColor={ui.theme.color.chipAccentBg} color={ui.theme.color.chipAccentText}>
              {' '}
              compose
              {' '}
            </Text>
            <Text color={ui.theme.color.panelMuted}> Enter send · Shift+Enter newline · / for commands</Text>
            {ui.bgTasks.size > 0 ? (
              <Text color={ui.theme.color.panelMuted}>
                {' '}
                · {ui.bgTasks.size} background {ui.bgTasks.size === 1 ? 'task' : 'tasks'}
              </Text>
            ) : null}
          </Box>

          {status.showStickyPrompt && (
            <Box
              backgroundColor={ui.theme.color.panelAltBg}
              borderColor={ui.theme.color.statusBorder}
              borderStyle="single"
              flexDirection="column"
              marginBottom={1}
              opaque
              paddingX={1}
              paddingY={0}
            >
              <Text color={ui.theme.color.panelMuted} wrap="truncate-end">
                <Text color={ui.theme.color.label}>context </Text>
                {status.stickyPrompt}
              </Text>
            </Box>
          )}

          <Box
            backgroundColor={ui.theme.color.panelAltBg}
            borderColor={sh ? ui.theme.color.shellDollar : ui.theme.color.statusBorder}
            borderStyle="single"
            flexDirection="column"
            opaque
            paddingX={1}
            paddingY={0}
          >
            {composer.inputBuf.map((line, i) => (
              <Box key={i}>
                <Box width={promptWidth}>
                  <Text color={ui.theme.color.dim}>{i === 0 ? ' │ ' : ' · '}</Text>
                </Box>

                <Text color={ui.theme.color.panelMuted}>{line || ' '}</Text>
              </Box>
            ))}

            <Box position="relative">
              <Box width={promptWidth}>
                {sh ? (
                  <Text color={ui.theme.color.shellDollar}> $ </Text>
                ) : (
                  <Text backgroundColor={ui.theme.color.chipAccentBg} color={ui.theme.color.chipAccentText}>
                    {' '}
                    {ui.theme.brand.prompt}
                    {' '}
                  </Text>
                )}
              </Box>

              <Box flexGrow={1} position="relative">
                <TextInput
                  columns={inputCols}
                  onChange={composer.updateInput}
                  onPaste={composer.handleTextPaste}
                  onSubmit={composer.submit}
                  placeholder={composer.empty ? PLACEHOLDER : ui.busy ? 'Ctrl+C to interrupt…' : ''}
                  value={composer.input}
                />

                <Box position="absolute" right={0}>
                  <GoodVibesHeart t={ui.theme} tick={status.goodVibesTick} />
                </Box>
              </Box>
            </Box>

            <Box marginTop={1}>
              <Text color={ui.theme.color.dim}>
                {ui.busy ? 'assistant is working · Ctrl+C interrupts the current run' : 'ready for the next prompt'}
              </Text>
            </Box>
          </Box>
        </Box>
      )}

      {!composer.empty && !ui.sid && <Text color={ui.theme.color.dim}>⚕ {ui.status}</Text>}
    </NoSelect>
  )
})

export const AppLayout = memo(function AppLayout({
  actions,
  composer,
  mouseTracking,
  progress,
  status,
  transcript
}: AppLayoutProps) {
  const ui = useStore($uiState)

  return (
    <AlternateScreen mouseTracking={mouseTracking}>
      <Box backgroundColor={ui.theme.color.surfaceBg} flexDirection="column" flexGrow={1} opaque>
        <Box flexDirection="row" flexGrow={1}>
          <TranscriptPane cols={composer.cols} progress={progress} setStickyPrompt={actions.setStickyPrompt} transcript={transcript} />
        </Box>

        <PromptZone
          cols={composer.cols}
          onApprovalChoice={actions.answerApproval}
          onClarifyAnswer={actions.answerClarify}
          onSecretSubmit={actions.answerSecret}
          onSudoSubmit={actions.answerSudo}
        />

        <ComposerPane actions={actions} composer={composer} status={status} />
      </Box>
    </AlternateScreen>
  )
})

interface StreamingAssistantProps {
  busy: boolean
  cols: number
  compact?: boolean
  detailsMode: DetailsMode
  progress: AppLayoutProgressProps
  t: Theme
}
