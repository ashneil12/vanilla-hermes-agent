import { useStore } from '@nanostores/react'
import { useEffect } from 'react'

import { BrandMark } from '@/components/brand-mark'
// hermes-fork: HermesOS is centrally managed (image rebuild + redeploy), so the
// in-app self-update controls are intentionally absent. We keep ONLY the imports
// the passive "automatic updates" note needs — do NOT re-take upstream's
// self-update UI imports (Button/Codicon/checkUpdates/startActiveUpdate/etc.).
import { useI18n } from '@/i18n'
import { RefreshCw } from '@/lib/icons'
import { $desktopVersion, refreshDesktopVersion } from '@/store/updates'

import { ListRow, SectionHeading, SettingsContent } from './primitives'
import { UninstallSection } from './uninstall-section'

export function AboutSettings() {
  const { t } = useI18n()
  const a = t.settings.about
  const version = useStore($desktopVersion)

  // The version atom is loaded once at app boot; re-read on mount so opening
  // About always reflects the running build.
  useEffect(() => {
    void refreshDesktopVersion()
  }, [])

  return (
    <SettingsContent>
      <div className="flex flex-col items-center gap-3 pt-6 pb-2 text-center">
        <BrandMark className="size-16" />
        <div>
          <h2 className="text-lg font-semibold tracking-tight">{a.heading}</h2>
          <p className="mt-1 text-xs text-muted-foreground">
            {version?.appVersion ? a.version(version.appVersion) : a.versionUnavailable}
          </p>
        </div>
      </div>

      <div className="mx-auto mt-4 w-full max-w-2xl">
        <SectionHeading icon={RefreshCw} title={a.updates} />

        {/* hermes-fork (case D — kept over upstream's 06-24/25 self-update
            overlay re-add): HermesOS is managed — the agent/backend is updated
            centrally (image rebuild + redeploy). The in-app self-update controls
            (check / "see what's new" / "update now") were removed so users aren't
            funnelled into the `hermes update` path; this stays as a passive,
            non-actionable note. */}
        <ListRow description={a.automaticUpdatesDesc} title={a.automaticUpdates} />

        <UninstallSection />
      </div>
    </SettingsContent>
  )
}
