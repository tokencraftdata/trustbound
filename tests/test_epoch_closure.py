from dataclasses import replace

from trustbound.epoch import (
    FencedProcessor,
    LogWitness,
    ProcessorClosure,
    audit_epoch_vector,
    indistinguishable_unfenced_runs,
    verify_statement,
)


def _closed(tmp_path, processor_id="flight-processor", amount=100):
    processor = FencedProcessor(processor_id, tmp_path / f"{processor_id}.db")
    processor.open_epoch("trip-epoch-1")
    processor.admit("trip-epoch-1", f"{processor_id}-p1", "flight", amount, 1)
    processor.reconcile(f"{processor_id}-p1", "confirmed", f"rail-{processor_id}-1")
    statement = processor.close_epoch("trip-epoch-1")
    return processor, statement


def test_admission_fence_rejects_post_close_payment(tmp_path):
    processor, _ = _closed(tmp_path)
    try:
        processor.admit("trip-epoch-1", "late", "flight", 10, 1)
        assert False, "post-close admission was accepted"
    except RuntimeError as exc:
        assert str(exc) == "epoch_closed_or_unknown"


def test_closure_has_gap_free_high_watermark(tmp_path):
    processor = FencedProcessor("processor", tmp_path / "processor.db")
    processor.open_epoch("e1")
    processor.admit("e1", "p1", "flight", 100, 1)
    processor.admit("e1", "p2", "flight", 200, 2)
    processor.reconcile("p1", "confirmed", "rail-1")
    statement = processor.close_epoch("e1")
    assert statement.high_watermark == 2
    assert [e.sequence for e in statement.entries] == [1, 2]
    assert statement.entries[1].status == "uncertain"


def test_uncertain_receipt_retains_full_liability(tmp_path):
    processor = FencedProcessor("processor", tmp_path / "processor.db")
    processor.open_epoch("e1")
    processor.admit("e1", "p1", "flight", 350, 1)
    statement = processor.close_epoch("e1")
    verified = verify_statement(statement, processor.public_key)
    assert verified.valid
    assert verified.liability_minor == 350


def test_released_payment_has_zero_liability(tmp_path):
    processor = FencedProcessor("processor", tmp_path / "processor.db")
    processor.open_epoch("e1")
    processor.admit("e1", "p1", "flight", 350, 1)
    processor.reconcile("p1", "released", None)
    verified = verify_statement(processor.close_epoch("e1"), processor.public_key)
    assert verified.valid
    assert verified.liability_minor == 0


def test_tampered_entry_invalidates_processor_signature(tmp_path):
    processor, statement = _closed(tmp_path)
    changed_entry = replace(statement.entries[0], amount_minor=1)
    tampered = replace(statement, entries=(changed_entry,))
    assert not verify_statement(tampered, processor.public_key).valid


def test_sequence_gap_is_rejected(tmp_path):
    processor, statement = _closed(tmp_path)
    changed_entry = replace(statement.entries[0], sequence=2)
    tampered = replace(statement, entries=(changed_entry,), high_watermark=2)
    result = verify_statement(tampered, processor.public_key)
    assert not result.valid
    assert result.reason == "sequence_gap"


def test_witness_refuses_processor_equivocation(tmp_path):
    processor, statement = _closed(tmp_path)
    witness = LogWitness("w1", tmp_path / "w1.db")
    witness.attest(statement, processor.public_key)
    alternate = replace(statement, root="0" * 64)
    try:
        witness.attest(alternate, processor.public_key)
        assert False, "invalid alternate checkpoint was accepted"
    except ValueError:
        pass


def test_auditor_requires_every_processor_closure(tmp_path):
    processor, statement = _closed(tmp_path)
    witness = LogWitness("w1", tmp_path / "w1.db")
    attestation = witness.attest(statement, processor.public_key)
    result = audit_epoch_vector(
        [ProcessorClosure(statement, (attestation,))],
        {"flight-processor", "hotel-processor"},
        {"flight-processor": processor.public_key},
        {"w1": witness.public_key},
        1,
        1_000,
    )
    assert not result.valid
    assert result.reason == "processor_set_incomplete"


def test_two_processor_vector_verifies_with_independent_databases(tmp_path):
    flight, flight_statement = _closed(tmp_path, "flight-processor", 400)
    hotel, hotel_statement = _closed(tmp_path, "hotel-processor", 500)
    w1 = LogWitness("w1", tmp_path / "w1.db")
    w2 = LogWitness("w2", tmp_path / "w2.db")
    closures = []
    for processor, statement in ((flight, flight_statement), (hotel, hotel_statement)):
        closures.append(
            ProcessorClosure(
                statement,
                (w1.attest(statement, processor.public_key), w2.attest(statement, processor.public_key)),
            )
        )
    result = audit_epoch_vector(
        closures,
        {"flight-processor", "hotel-processor"},
        {"flight-processor": flight.public_key, "hotel-processor": hotel.public_key},
        {"w1": w1.public_key, "w2": w2.public_key},
        2,
        1_000,
    )
    assert result.valid
    assert result.liability_minor == 900
    assert flight.path != hotel.path


def test_vector_rejects_aggregate_liability_over_budget(tmp_path):
    flight, flight_statement = _closed(tmp_path, "flight-processor", 600)
    hotel, hotel_statement = _closed(tmp_path, "hotel-processor", 600)
    witness = LogWitness("w1", tmp_path / "w1.db")
    closures = [
        ProcessorClosure(flight_statement, (witness.attest(flight_statement, flight.public_key),)),
        ProcessorClosure(hotel_statement, (witness.attest(hotel_statement, hotel.public_key),)),
    ]
    result = audit_epoch_vector(
        closures,
        {"flight-processor", "hotel-processor"},
        {"flight-processor": flight.public_key, "hotel-processor": hotel.public_key},
        {"w1": witness.public_key},
        1,
        1_000,
    )
    assert not result.valid
    assert result.reason == "budget_exceeded"


def test_unfenced_hidden_effect_is_indistinguishable():
    clean, attacked = indistinguishable_unfenced_runs()
    assert clean["evidence"] == attacked["evidence"]
    assert clean["ground_truth_effects"] != attacked["ground_truth_effects"]
