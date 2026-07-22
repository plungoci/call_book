"""Unit tests for propagation defaults; no graphical display is required."""
import unittest

from services.propagation_service import (
    PROPAGATION_DIRECT, PROPAGATION_F2, PROPAGATION_METEOR_SCATTER,
    PROPAGATION_NVIS, PROPAGATION_REPEATER, PROPAGATION_SATELLITE,
    PROPAGATION_SPORADIC_E, PROPAGATION_UNKNOWN, PropagationSuggestionState,
    suggest_propagation_mode,
)


class PropagationServiceTests(unittest.TestCase):
    def test_hf_defaults(self):
        self.assertEqual(suggest_propagation_mode("20 m"), PROPAGATION_F2)
        self.assertEqual(suggest_propagation_mode("40m"), PROPAGATION_NVIS)
        self.assertEqual(suggest_propagation_mode("80 M"), PROPAGATION_NVIS)

    def test_vhf_uhf_defaults(self):
        self.assertEqual(suggest_propagation_mode("6m"), PROPAGATION_SPORADIC_E)
        self.assertEqual(suggest_propagation_mode("2 m"), PROPAGATION_DIRECT)
        self.assertEqual(suggest_propagation_mode("70 CM"), PROPAGATION_DIRECT)

    def test_repeater_and_satellite_take_priority(self):
        self.assertEqual(suggest_propagation_mode("2m", repeater_selected=True), PROPAGATION_REPEATER)
        self.assertEqual(suggest_propagation_mode("70cm", repeater_selected=True), PROPAGATION_REPEATER)
        self.assertEqual(suggest_propagation_mode("2m", satellite_selected=True), PROPAGATION_SATELLITE)
        self.assertEqual(suggest_propagation_mode("70cm", satellite_selected=True), PROPAGATION_SATELLITE)
        self.assertEqual(suggest_propagation_mode("2m", repeater_selected=True, satellite_selected=True), PROPAGATION_SATELLITE)

    def test_msk_and_fm_rules(self):
        self.assertEqual(suggest_propagation_mode("2m", mode="MSK144"), PROPAGATION_METEOR_SCATTER)
        self.assertEqual(suggest_propagation_mode("6m", mode="MSK144"), PROPAGATION_METEOR_SCATTER)
        self.assertEqual(suggest_propagation_mode("6m", mode="FM"), PROPAGATION_DIRECT)
        self.assertEqual(suggest_propagation_mode("6m", mode="SSB"), PROPAGATION_SPORADIC_E)

    def test_unknown_missing_and_normalized_bands(self):
        self.assertEqual(suggest_propagation_mode("unknown"), PROPAGATION_UNKNOWN)
        self.assertEqual(suggest_propagation_mode(None), PROPAGATION_UNKNOWN)
        self.assertEqual(suggest_propagation_mode(" 1,25 m "), PROPAGATION_DIRECT)
        self.assertEqual(suggest_propagation_mode("20 M", frequency_mhz=None), PROPAGATION_F2)

    def test_network_mode_is_not_replaced_by_direct(self):
        self.assertEqual(suggest_propagation_mode("2m", mode="DMR"), "DMR")


class PropagationSuggestionStateTests(unittest.TestCase):
    def test_manual_value_is_protected(self):
        state = PropagationSuggestionState(); state.mark_manual()
        self.assertFalse(state.may_apply(PROPAGATION_DIRECT))

    def test_new_qso_resets_manual_protection(self):
        state = PropagationSuggestionState(manually_selected=True)
        state.reset_for_new_qso()
        self.assertTrue(state.may_apply(PROPAGATION_DIRECT))

    def test_existing_qso_is_preserved_on_load(self):
        state = PropagationSuggestionState(); state.load_existing_qso()
        self.assertFalse(state.may_apply(PROPAGATION_F2))

    def test_forced_recalculation_and_significant_context_override(self):
        state = PropagationSuggestionState(manually_selected=True)
        self.assertTrue(state.may_apply(PROPAGATION_F2, force=True))
        self.assertTrue(state.may_apply(PROPAGATION_REPEATER))
        self.assertTrue(state.may_apply(PROPAGATION_SATELLITE))


if __name__ == "__main__":
    unittest.main()
