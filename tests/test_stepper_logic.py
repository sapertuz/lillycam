"""Tests for the stepper full-step sequence logic (no hardware required)."""

from lillycam.stepper import _STEP_SEQ


def test_sequence_length():
    """Full-step sequence has exactly 4 states (one per coil)."""
    assert len(_STEP_SEQ) == 4


def test_each_state_has_four_pins():
    """Each state drives exactly 4 coil pins."""
    for state in _STEP_SEQ:
        assert len(state) == 4


def test_each_state_has_exactly_one_active():
    """Full-step energizes exactly one coil per state."""
    for state in _STEP_SEQ:
        assert sum(state) == 1


def test_sequence_is_cyclic():
    """Forward stepping wraps around correctly (state 3 -> state 0)."""
    last_idx = len(_STEP_SEQ) - 1
    next_idx = (last_idx + 1) % len(_STEP_SEQ)
    assert next_idx == 0
    assert _STEP_SEQ[0] == (1, 0, 0, 0)


def test_stepper_step_calls_gpio(gpio):
    """Stepper.step() drives the GPIO output pins."""
    from lillycam.stepper import Stepper

    stepper = Stepper()
    stepper.step(1, delay=0)

    # GPIO.output should have been called for each pin in one step
    assert gpio.output.called


def test_stepper_deenergize_on_close(gpio):
    """Stepper.close() de-energizes all coils."""
    from lillycam.stepper import Stepper
    from lillycam import pins

    stepper = Stepper()
    stepper.close()

    # Each pin in STEPPER_PINS should be set LOW
    low_calls = [
        call for call in gpio.output.call_args_list
        if call.args[1] == gpio.LOW
    ]
    assert len(low_calls) >= len(pins.STEPPER_PINS)
