import json
import pytest
from trustbound.credential_service import CommandService, SyntheticProvider, decode_request, intent
from trustbound.stripe_gate import StripeGate


@pytest.mark.parametrize("raw", [
    b'{"op":"dispatch","command_id":true}', b'{"op":"dispatch","command_id":"1"}',
    b'{"op":"dispatch","command_id":1.0}', b'{"op":"dispatch","command_id":-1}',
    b'{"op":"dispatch","command_id":2147483648}', b'{"op":"dispatch","command_id":NaN}',
    b'{"op":"snapshot","op":"dispatch","command_id":1}',
    b'{"op":"dispatch","command_id":1,"path":"/v1/payment_intents"}',
    b'{"op":"dispatch","command_id":1,"amount":999999}',
    b'{"op":"dispatch","command_id":1,"transport":"attacker"}',
    b'{"op":"observe","status":"canceled"}', b'{"op":"grant","payment_id":"pi_Other"}',
    b'{"op":"create","confirm":true}', b'{"op":"fence","closed":false}',
    b'{"op":"read","path":"/run/secrets/provider-key"}', b'[]', b'null', b'{}',
    b'__import__("os").system("true")', b'\xff', b' ' * 4097,
])
def test_untrusted_schema_rejected(raw):
    with pytest.raises((ValueError, UnicodeError)):
        decode_request(raw)


def test_authorized_command_and_authoritative_reconciliation(tmp_path):
    gate = StripeGate(tmp_path / "gate.db", "epoch")
    gate.register(intent())
    gate.grant("pi_Boundary1", "capture")
    gate.fence()
    secret = "TB_BOUNDARY_CANARY_TEST_ONLY"
    provider = SyntheticProvider(tmp_path / "provider.db", secret)
    service = CommandService(gate, provider)
    assert not service.handle(b'{"op":"observe","status":"canceled"}')["ok"]
    assert not service.handle(b'{"op":"dispatch","command_id":42}')["ok"]
    first = service.handle(b'{"op":"dispatch","command_id":1}')
    assert first["ok"] and secret not in json.dumps(first)
    assert not service.handle(b'{"op":"dispatch","command_id":1}')["ok"]
    assert not service.handle(b'{"op":"snapshot"}')["result"]["known_manifest_resolved"]
    final = service.handle(b'{"op":"reconcile"}')["result"]
    assert final["known_manifest_resolved"] and not final["deployment_completeness_proved"]
    assert final["retained_minor"] == 200
    assert provider.db.execute("SELECT COUNT(*) FROM effect").fetchone()[0] == 1
    gate.close()
    provider.db.close()


def test_provider_exception_is_not_an_agent_response(tmp_path):
    class Faulty:
        def request(self, *args):
            raise RuntimeError("TB_BOUNDARY_CANARY_PRIVATE")
    gate = StripeGate(tmp_path / "gate.db", "epoch")
    gate.register(intent())
    gate.grant("pi_Boundary1", "capture")
    reply = CommandService(gate, Faulty()).handle(b'{"op":"dispatch","command_id":1}')
    assert reply == {"ok": False, "error": "request_rejected_or_unresolved"}
    assert gate.db.execute("SELECT claimed FROM command").fetchone() == (1,)
    gate.close()
