"""Driver registry and metadata."""

from typing import Dict, List

from app.services.payments.base import PaymentDriver, ProviderMeta
from app.services.payments.cashfree import CashfreeDriver
from app.services.payments.demo import DemoDriver
from app.services.payments.paytm import PaytmDriver
from app.services.payments.payu import PayUDriver
from app.services.payments.phonepe import PhonePeDriver
from app.services.payments.razorpay import RazorpayDriver

DRIVERS: Dict[str, PaymentDriver] = {
    d.meta.driver: d
    for d in (
        DemoDriver(),
        RazorpayDriver(),
        CashfreeDriver(),
        PaytmDriver(),
        PhonePeDriver(),
        PayUDriver(),
    )
}


def get_driver(name: str) -> PaymentDriver:
    driver = DRIVERS.get(name)
    if not driver:
        raise ValueError(f"Unknown payment driver: {name}")
    return driver


def metadata() -> List[ProviderMeta]:
    return [d.meta for d in DRIVERS.values()]
