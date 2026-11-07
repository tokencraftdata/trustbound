FROM python:3.12-slim
ENV PYTHONPATH=/app PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY stripe_gate.py credential_service.py /app/trustbound/
COPY adversarial_agent.py /app/
USER 1000:1000
CMD ["python", "-m", "trustbound.credential_service", "--socket", "/run/gate/control.sock", "--state", "/state", "--credential", "/run/secrets/provider-key"]
