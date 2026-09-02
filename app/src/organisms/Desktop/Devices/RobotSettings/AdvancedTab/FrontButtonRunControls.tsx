import { useTranslation } from 'react-i18next'
import { useDispatch } from 'react-redux'

import { LegacyStyledText, SPACING, TYPOGRAPHY } from '@opentrons/components'

import { ToggleButton } from '/app/atoms/buttons'
import { updateSetting } from '/app/redux/robot-settings'

import styles from './frontbuttonruncontrols.module.css'

import type { MouseEventHandler } from 'react'
import type { RobotSettingsField } from '/app/redux/robot-settings/types'
import type { Dispatch } from '/app/redux/types'

interface FrontButtonRunControlsProps {
  settings?: RobotSettingsField
  robotName: string
  isRobotBusy: boolean
}

export function FrontButtonRunControls({
  settings,
  robotName,
  isRobotBusy,
}: FrontButtonRunControlsProps): JSX.Element {
  const { t } = useTranslation('device_settings')
  const dispatch = useDispatch<Dispatch>()
  const value = settings?.value ?? false
  const id = settings?.id ?? 'disableOT2FrontButton'

  const handleClick: MouseEventHandler<Element> = () => {
    if (!isRobotBusy) {
      dispatch(updateSetting(robotName, id, !value))
    }
  }

  return (
    <div className={styles.container}>
      <div className={styles.text_container}>
        <LegacyStyledText
          forwardedAs="p"
          fontWeight={TYPOGRAPHY.fontWeightSemiBold}
          marginBottom={SPACING.spacing4}
          id="AdvancedSettings_frontButtonRunControls"
        >
          {t('front_button_run_controls')}
        </LegacyStyledText>
        <LegacyStyledText forwardedAs="p">
          {t('front_button_run_controls_description')}
        </LegacyStyledText>
      </div>
      <ToggleButton
        label="front_button_run_controls"
        toggledOn={!value}
        onClick={handleClick}
        id="RobotSettings_frontButtonRunControlsToggleButton"
        disabled={isRobotBusy}
      />
    </div>
  )
}
