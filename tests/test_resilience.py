from woo_connector.models.errors import CircuitOpenError
from woo_connector.resilience.circuit_breaker import CircuitBreaker


def test_circuit_breaker_opens_and_recovers():
    now = [0.0]
    breaker = CircuitBreaker(failure_threshold=2, reset_after_s=10, clock=lambda: now[0])

    breaker.before_call()
    breaker.record_failure()
    assert breaker.state == "closed"

    breaker.before_call()
    breaker.record_failure()
    assert breaker.state == "open"

    try:
        breaker.before_call()
    except CircuitOpenError as exc:
        assert exc.retry_after_s == 10
    else:
        raise AssertionError("expected open circuit")

    now[0] = 10.0
    assert breaker.state == "half_open"
    breaker.before_call()
    breaker.record_success()
    assert breaker.state == "closed"
