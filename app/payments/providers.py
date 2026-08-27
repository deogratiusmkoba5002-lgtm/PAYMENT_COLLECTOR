"""
Payment provider abstraction.

For the MVP only SimulatedProvider is implemented. Real providers
(Selcom, M-Pesa, Airtel Money, etc.) should be added here as new classes
implementing the same interface, without touching routes.py or models.py.
"""
from abc import ABC, abstractmethod


class PaymentProvider(ABC):
    @abstractmethod
    def initiate_payment(self, contribution):
        """Start a payment. Return a dict with at least {'status': ...}."""
        raise NotImplementedError

    @abstractmethod
    def verify_payment(self, contribution, callback_data):
        """Verify a provider callback/webhook and return the confirmed status."""
        raise NotImplementedError


class SimulatedProvider(PaymentProvider):
    def initiate_payment(self, contribution):
        return {"status": "pending", "provider_reference": contribution.reference_id}

    def verify_payment(self, contribution, callback_data):
        # A real provider would validate a signature/webhook payload here
        # before confirming. This simulates that confirmation step.
        result = callback_data.get("simulated_result", "successful")
        return result if result in ("successful", "failed") else "failed"


def get_active_provider():
    # Swap this for a real provider once integrated, e.g. based on
    # an env var like PAYMENT_PROVIDER=selcom
    return SimulatedProvider()