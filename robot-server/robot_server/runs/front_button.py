"""Control protocol runs with the OT-2 front button."""

import asyncio
import logging
from dataclasses import dataclass
from typing import Awaitable, Callable
from uuid import uuid4

from opentrons.hardware_control.types import (
    FrontButtonPressNotification,
    HardwareEvent,
)
from opentrons.protocol_engine.types import EngineStatus
from opentrons.util.helpers import utc_now

from .action_models import RunActionType
from .run_controller import RunController

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class CurrentRun:
    """The state and controller for the current run."""

    status: EngineStatus
    controller: RunController


ResolveCurrentRun = Callable[[], Awaitable[CurrentRun | None]]
"""Get the current run, if one exists."""


class FrontButtonListener:
    """Pause and resume the current run in response to front-button presses."""

    def __init__(
        self,
        resolve_current_run: ResolveCurrentRun,
    ) -> None:
        self._resolve_current_run = resolve_current_run
        self._loop = asyncio.get_running_loop()
        self._action_lock = asyncio.Lock()

    def handle_hardware_event(self, event: HardwareEvent) -> None:
        """Schedule a button press for handling on the robot-server event loop.

        This is used as a callback for `HardwareControlAPI.register_callback()`,
        so it may run in the hardware API's thread. It returns immediately; the
        press is handled later on the robot-server event loop.
        """
        if isinstance(event, FrontButtonPressNotification):
            asyncio.run_coroutine_threadsafe(self._handle_press_safely(), self._loop)

    async def _handle_press_safely(self) -> None:
        try:
            await self._handle_press()
        except Exception:
            log.exception("Exception handling an OT-2 front button press.")

    async def _handle_press(self) -> None:
        """Toggle a running or paused run."""
        async with self._action_lock:
            current_run = await self._resolve_current_run()
            if current_run is None:
                return

            if current_run.status == EngineStatus.RUNNING:
                action_type = RunActionType.PAUSE
            elif current_run.status == EngineStatus.PAUSED:
                action_type = RunActionType.PLAY
            else:
                return

            log.info(f"Issuing {action_type} from the OT-2 front button.")
            current_run.controller.create_action(
                action_id=str(uuid4()),
                action_type=action_type,
                created_at=utc_now(),
                action_payload=None,
            )
