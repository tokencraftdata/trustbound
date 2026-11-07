from trustbound.observer_experiment import accepts, covered, enumerate_model, faithful


def test_exhaustive_two_observers_two_paths():
    result = enumerate_model()
    assert result["policy_observation_coalition_cases"] == 1024
    assert result["truth_report_valuations"] == 65536
    assert result["equivalence_mismatches"] == 0
    assert result["covered_cases"] > 0
    assert result["unsafe_cases"] > 0
    for row in result["records"]:
        if not row["robust"]:
            bad = row["counterexample"]
            assert bad["good_paths"] != 3
            assert accepts(row["required"], bad["positive_reports"])
            assert faithful(bad["positive_reports"], row["observes"], row["corrupt"],
                            bad["good_paths"], 2, 2)


def test_honest_mirror_does_not_repair_corrupt_sole_source():
    assert accepts(0b11, 0b11)
    assert faithful(0b11, 0b01, 0b01, 0, 2, 1)
    assert not covered(0b11, 0b01, 0b01, 2, 1)


def test_two_effect_observers_tolerate_either_single_fault():
    for corrupt in (0b01, 0b10):
        assert covered(0b11, 0b11, corrupt, 2, 1)
        assert not faithful(0b11, 0b11, corrupt, 0, 2, 1)


def test_global_signer_count_is_not_path_coverage():
    # Two honest signers both see path 0; neither sees path 1.
    assert accepts(0b1111, 0b1111)
    assert faithful(0b1111, 0b0101, 0, 0b01, 2, 2)
    assert not covered(0b1111, 0b0101, 0, 2, 2)


def test_honest_observer_outside_accepted_set_cannot_help():
    assert accepts(0b01, 0b01)
    assert faithful(0b01, 0b11, 0b01, 0, 2, 1)
    assert not covered(0b01, 0b11, 0b01, 2, 1)


def test_finite_delays_defeat_every_tested_silence_timeout():
    # Finite illustration only; the arbitrary-time result is in Lean.
    for stop in range(100):
        arrival = stop + 1
        clean = tuple(False for _ in range(stop + 1))
        hidden = tuple(step >= arrival for step in range(stop + 1))
        assert hidden == clean
        assert not stop >= arrival
        assert arrival >= arrival  # the report DOES eventually arrive
