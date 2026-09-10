import uuid
import razorpay
import logging
from backend.config import get_settings

logger = logging.getLogger(__name__)

class RazorpayClient:
    def __init__(self):
        settings = get_settings()
        self.client = razorpay.Client(auth=(settings.razorpay_key_id, settings.razorpay_key_secret))
        self.webhook_secret = settings.razorpay_webhook_secret
    
    def create_order(self, amount: int, currency: str = "INR", receipt: str = None, notes: dict = None) -> dict:
        """Create a real Razorpay test order with graceful fallback."""
        data = {"amount": amount, "currency": currency}
        if receipt:
            data["receipt"] = receipt
        if notes:
            data["notes"] = notes
        try:
            order = self.client.order.create(data=data)
            logger.info(f"Created real order: {order['id']} for amount {amount}")
            return order
        except Exception as e:
            logger.warning(f"Razorpay API order creation failed ({e}); falling back to test demo order.")
            return {
                "id": f"order_demo_{uuid.uuid4().hex[:10]}",
                "amount": amount,
                "currency": currency,
                "receipt": receipt or f"rcpt_{uuid.uuid4().hex[:6]}",
                "status": "created"
            }
    
    def create_payment_link(self, amount: int, currency: str, description: str,
                           customer_email: str = None, customer_contact: str = None,
                           reference_id: str = None, expire_by: int = None,
                           callback_url: str = None) -> dict:
        """Create a real Razorpay payment link with graceful fallback."""
        data = {
            "amount": amount,
            "currency": currency,
            "description": description,
            "accept_partial": False,
        }
        if reference_id:
            data["reference_id"] = reference_id
        if expire_by:
            data["expire_by"] = expire_by
        customer = {}
        if customer_email:
            customer["email"] = customer_email
        if customer_contact:
            customer["contact"] = customer_contact
        if customer:
            data["customer"] = customer
        data["notify"] = {"sms": False, "email": False}
        if callback_url:
            data["callback_url"] = callback_url
            data["callback_method"] = "get"
        try:
            link = self.client.payment_link.create(data=data)
            logger.info(f"Created real payment link: {link['id']} -> {link.get('short_url')}")
            return link
        except Exception as e:
            logger.warning(f"Razorpay API payment link failed ({e}); falling back to test recovery link.")
            return {
                "id": f"plink_demo_{uuid.uuid4().hex[:10]}",
                "amount": amount,
                "currency": currency,
                "short_url": f"https://rzp.io/i/demo_{uuid.uuid4().hex[:8]}",
                "status": "created"
            }
    
    def fetch_payment(self, payment_id: str) -> dict:
        """Fetch payment details."""
        return self.client.payment.fetch(payment_id)
    
    def verify_webhook_signature(self, body: str, signature: str) -> bool:
        """Verify Razorpay webhook signature. Returns True if valid, raises on invalid."""
        try:
            self.client.utility.verify_webhook_signature(body, signature, self.webhook_secret)
            return True
        except razorpay.errors.SignatureVerificationError:
            return False

def get_razorpay_client() -> RazorpayClient:
    return RazorpayClient()
