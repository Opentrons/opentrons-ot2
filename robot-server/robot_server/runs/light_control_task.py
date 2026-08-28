"""Background task to drive the Flex's status bar."""

import asyncio
import time
from dataclasses import dataclass
from logging import getLogger
from typing import Callable, List, Optional

from opentrons.hardware_control import HardwareControlAPI
from opentrons.hardware_control.types import (
    EstopState,
    StatusBarState,
    SubSystem,
    UpdateState,
)
from opentrons.protocol_engine.types import EngineStatus

from .run_orchestrator_store import RunOrchestratorStore

log = getLogger(__name__)

# A double-blink followed by a longer pause, to distinguish a paused run from the
# even on/off blinking that FrontButtonLightBlinker does during boot.
_OT2_BUTTON_BLINK_PATTERN = (True, False, True, False, False, False)
_OT2_BUTTON_BLINK_PERIOD_S = 2.0


@dataclass
class Status:
    """Class to encapsulate overall status of the system as it pertains to the light control task."""

    active_updates: List[SubSystem]
    estop_status: EstopState
    engine_status: Optional[EngineStatus]


def _engine_status_to_status_bar(
    status: Optional[EngineStatus],
    initialization_done: bool,
) -> StatusBarState:
    """Convert an engine status into a status bar status."""
    match status:
        case None | EngineStatus.IDLE:
            return StatusBarState.IDLE if initialization_done else StatusBarState.OFF
        case EngineStatus.RUNNING:
            return StatusBarState.RUNNING
        case EngineStatus.PAUSED | EngineStatus.BLOCKED_BY_OPEN_DOOR:
            return StatusBarState.PAUSED
        case (
            EngineStatus.AWAITING_RECOVERY
            | EngineStatus.AWAITING_RECOVERY_PAUSED
            | EngineStatus.AWAITING_RECOVERY_BLOCKED_BY_OPEN_DOOR
        ):
            return StatusBarState.ERROR_RECOVERY
        case EngineStatus.STOP_REQUESTED | EngineStatus.FINISHING:
            return StatusBarState.UPDATING
        case EngineStatus.STOPPED:
            return StatusBarState.IDLE
        case EngineStatus.FAILED:
            return StatusBarState.HARDWARE_ERROR
        case EngineStatus.SUCCEEDED:
            return StatusBarState.RUN_COMPLETED


def _active_updates_to_status_bar(
    previous: List[SubSystem],
    current: List[SubSystem],
    initialization_done: bool,
    force_value: bool,
) -> Optional[StatusBarState]:
    """Based on how the set of active updates has changed, see if the status bar should change.

    It is important NOT to re-set the Updating state every time the list of updating subsystems
    changes, because that will result in the pulsing looking incorrect. Instead, only update if
    the list changed between empty/not empty, OR if the rear panel just finished updating (because
    we can only set the status if the rear panel is active!).
    """
    if previous == current and not force_value:
        return None
    if SubSystem.rear_panel in current:
        # We cannot set anything if the rear panel is updating
        return None
    if len(current) == 0:
        # We just finished updating, put status bar in normal mode.
        # Note that if this is the initial set of updates we want to set the bar Off,
        # so act accordingly.
        return StatusBarState.IDLE if initialization_done else StatusBarState.OFF
    elif len(previous) == 0 or SubSystem.rear_panel in previous or force_value:
        # We either just finished updating the rear panel OR we just started running
        # updates. Either way, the status bar should (re)start the Updating animation.
        return StatusBarState.UPDATING
    return None


class LightController:
    """LightController sets the Flex's status bar or OT-2's front button light to match protocol status."""

    def __init__(
        self,
        api: HardwareControlAPI,
        run_orchestrator_store: Optional[RunOrchestratorStore],
        ot2_front_button_enabled: bool,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        """Create a new LightController."""
        self._api = api
        self._run_orchestrator_store = run_orchestrator_store
        self._initialization_done = False
        self._ot2_front_button_enabled = ot2_front_button_enabled
        self._monotonic = monotonic
        self._ot2_button_light_on = True  # The light should have been left on after the boot process.

    def mark_initialization_done(self) -> None:
        """Called once the robot server hardware initialization finishes."""
        self._initialization_done = True

    def update_run_orchestrator_store(
        self, run_orchestrator_store: RunOrchestratorStore
    ) -> None:
        """Provide a handle to an EngineStore for the light control task."""
        self._run_orchestrator_store = run_orchestrator_store

    async def update(self, prev_status: Optional[Status], new_status: Status) -> None:
        """Update robot lights if the current run status has changed."""
        if self._ot2_front_button_enabled:
            await self._update_for_ot2(new_status)

        await self._update_for_flex(prev_status, new_status)

    async def _update_for_ot2(self, new_status: Status) -> None:
        """Blink the OT-2 front button while a run is paused; otherwise leave it."""
        should_blink = new_status.engine_status in {
            EngineStatus.PAUSED,
            EngineStatus.BLOCKED_BY_OPEN_DOOR,
        }
        if should_blink:
            step = int(
                self._monotonic()
                / (_OT2_BUTTON_BLINK_PERIOD_S / len(_OT2_BUTTON_BLINK_PATTERN))
            )
            button_light_should_be_on = _OT2_BUTTON_BLINK_PATTERN[
                step % len(_OT2_BUTTON_BLINK_PATTERN)
            ]
        else:
            button_light_should_be_on = True
        if button_light_should_be_on != self._ot2_button_light_on:
            self._ot2_button_light_on = button_light_should_be_on
            await self._api.set_lights(button=button_light_should_be_on)

    async def _update_for_flex(
        self, prev_status: Optional[Status], new_status: Status
    ) -> None:
        """Set the Flex status bar to match run, estop, and firmware-update status."""
        if prev_status == new_status:
            # No change, don't try to set anything.
            return

        if new_status.estop_status == EstopState.PHYSICALLY_ENGAGED:
            # Estop takes precedence
            await self._api.set_status_bar_state(state=StatusBarState.SOFTWARE_ERROR)
        elif len(new_status.active_updates) > 0:
            # Updates take precedence over the protocol status
            state = _active_updates_to_status_bar(
                previous=[] if prev_status is None else prev_status.active_updates,
                current=new_status.active_updates,
                initialization_done=self._initialization_done,
                force_value=True
                if prev_status is not None
                and prev_status.estop_status is EstopState.PHYSICALLY_ENGAGED
                else False,
            )
            if state is not None:
                await self._api.set_status_bar_state(state=state)
        else:
            # Active engine status
            await self._api.set_status_bar_state(
                state=_engine_status_to_status_bar(
                    status=new_status.engine_status,
                    initialization_done=self._initialization_done,
                )
            )

    def _get_current_engine_status(self) -> Optional[EngineStatus]:
        """Get the `status` value from the engine's active run engine."""
        if self._run_orchestrator_store is None:
            return None
        current_id = self._run_orchestrator_store.current_run_id
        if current_id is not None:
            return self._run_orchestrator_store.get_status()

        return None

    def _get_active_updates(self) -> List[SubSystem]:
        """Get any active firmware updates."""
        return [
            subsystem
            for subsystem, status in self._api.attached_subsystems.items()
            if status.update_state is not None
            and status.update_state is UpdateState.updating
        ]

    def get_current_status(self) -> Status:
        """Get the overall status of the system for light purposes."""
        return Status(
            active_updates=self._get_active_updates(),
            estop_status=self._api.get_estop_state(),
            engine_status=self._get_current_engine_status(),
        )


async def run_light_task(driver: LightController) -> None:
    """Run the light control task.

    This is intended to be run as a background task once the EngineStore has been created.
    """
    prev_status = driver.get_current_status()
    await driver.update(prev_status=None, new_status=prev_status)
    while True:
        await asyncio.sleep(0.1)
        new_status = driver.get_current_status()
        await driver.update(prev_status=prev_status, new_status=new_status)
        prev_status = new_status
