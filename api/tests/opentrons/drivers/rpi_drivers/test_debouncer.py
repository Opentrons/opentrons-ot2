"""Tests for Debouncer."""

import time

from decoy import Decoy

from opentrons.drivers.rpi_drivers._debouncer import Debouncer


def test_debouncer(decoy: Decoy) -> None:
    """It should accept triggers spaced outside the window and ignore the rest."""
    get_monotonic_seconds = decoy.mock(func=time.monotonic)
    subject = Debouncer(
        debounce_seconds=10, get_monotonic_seconds=get_monotonic_seconds
    )

    decoy.when(get_monotonic_seconds()).then_return(100)
    assert subject.trigger() is True

    decoy.when(get_monotonic_seconds()).then_return(104)
    assert subject.trigger() is False
    decoy.when(get_monotonic_seconds()).then_return(109)
    assert subject.trigger() is False
    decoy.when(get_monotonic_seconds()).then_return(111)
    assert subject.trigger() is True

    decoy.when(get_monotonic_seconds()).then_return(115)
    assert subject.trigger() is False
    decoy.when(get_monotonic_seconds()).then_return(120)
    assert subject.trigger() is False
    decoy.when(get_monotonic_seconds()).then_return(122)
    assert subject.trigger() is True
