import os
import json
import logging
from typing import Dict, Any
from urllib.parse import urljoin
import uuid

import requests
from flask import current_app

logger = logging.getLogger(__name__)

class For4PaymentsAPI:

    def __init__(self, secret_key: str = None):
        self.API_URL = "https://app.for4payments.com.br/api/v1"
        self.secret_key = secret_key or os.environ.get('FOR4PAYMENTS_SECRET_KEY')
        if not self.secret_key:
            raise ValueError("For4Payments secret key is required")

        # Log initialization with masked key
        masked_key = self.secret_key[:8] + "..." if self.secret_key else "None"
        logger.info(f"[For4Payments] Initializing with key: {masked_key}")

    def _get_headers(self) -> Dict[str, str]:
        return {
            'Authorization': self.secret_key,
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

    def _format_phone(self, phone: str) -> str:
        """Format phone number to match API requirements"""
        # Remove all non-digits
        clean_phone = ''.join(filter(str.isdigit, phone))
        logger.info(f"[Phone Formatting] Original: {phone} -> Formatted: {clean_phone}")
        return clean_phone

    def create_pix_payment(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new PIX payment

        Args:
            data (dict): Payment data containing:
                - amount (float): Payment amount
                - name (str): Customer name
                - email (str): Customer email
                - cpf (str): Customer CPF
                - phone (str): Customer phone
        """
        try:
            transaction_id = str(uuid.uuid4())
            logger.info(f"[For4Payments][{transaction_id}] Starting new payment transaction")
            logger.info(f"[For4Payments][{transaction_id}] Input data received:")

            # Mask sensitive data for logging
            masked_data = {
                **data,
                'cpf': f"{data['cpf'][:3]}****{data['cpf'][-2:]}",
                'email': f"{data['email'][:3]}***@{data['email'].split('@')[1]}"
            }
            logger.info(f"[For4Payments][{transaction_id}] Received data: {json.dumps(masked_data, indent=2)}")

            # Convert amount to cents
            amount_cents = int(float(data['amount']) * 100)
            logger.info(f"[For4Payments][{transaction_id}] Amount converted to cents: {amount_cents}")

            # Clean CPF
            clean_cpf = ''.join(filter(str.isdigit, data['cpf']))
            masked_cpf = f"{clean_cpf[:3]}****{clean_cpf[-2:]}"
            logger.info(f"[For4Payments][{transaction_id}] CPF cleaned: {masked_cpf}")

            # Format phone
            formatted_phone = self._format_phone(data['phone'])
            logger.info(f"[For4Payments][{transaction_id}] Phone formatted: {formatted_phone}")

            payment_data = {
                'name': data['name'],
                'email': data['email'],
                'cpf': clean_cpf,
                'phone': formatted_phone,
                'paymentMethod': 'PIX',
                'amount': amount_cents,
                'items': [{
                    'title': 'tarifa transacional',
                    'quantity': 1,
                    'unitPrice': amount_cents,
                    'tangible': False
                }]
            }

            logger.info(f"[For4Payments][{transaction_id}] Prepared request data: {json.dumps(payment_data, indent=2)}")

            # Log request headers (excluding Authorization)
            headers = self._get_headers()
            safe_headers = {k: v for k, v in headers.items() if k.lower() != 'authorization'}
            logger.info(f"[For4Payments][{transaction_id}] Request headers: {json.dumps(safe_headers, indent=2)}")

            response = requests.post(
                urljoin(self.API_URL, 'transaction.purchase'),
                headers=self._get_headers(),
                json=payment_data
            )

            logger.info(f"[For4Payments][{transaction_id}] Response status code: {response.status_code}")
            logger.info(f"[For4Payments][{transaction_id}] Response headers: {json.dumps(dict(response.headers), indent=2)}")

            if response.status_code != 200:
                error_msg = f"Payment API error ({response.status_code}): {response.text}"
                logger.error(f"[For4Payments][{transaction_id}] {error_msg}")
                raise ValueError(error_msg)

            result = response.json()
            logger.info(f"[For4Payments][{transaction_id}] Success response: {json.dumps(result, indent=2)}")

            return {
                'id': result['id'],
                'pixCode': result['pixCode'],
                'pixQrCode': result['pixQrCode'],
                'expiresAt': result['expiresAt'],
                'status': result.get('status', 'pending')
            }

        except Exception as e:
            logger.error(f"[For4Payments] Error creating payment: {str(e)}")
            raise

    def check_payment_status(self, payment_id: str) -> Dict[str, str]:
        """Check the status of a payment"""
        try:
            logger.info(f"[For4Payments] Checking payment status for ID: {payment_id}")

            # Log request headers (excluding Authorization)
            headers = self._get_headers()
            safe_headers = {k: v for k, v in headers.items() if k.lower() != 'authorization'}
            logger.info(f"[For4Payments] Status check request headers: {json.dumps(safe_headers, indent=2)}")

            response = requests.get(
                urljoin(self.API_URL, 'transaction.getPayment'),
                headers=self._get_headers(),
                params={'id': payment_id}
            )

            logger.info(f"[For4Payments] Status check response code: {response.status_code}")
            logger.info(f"[For4Payments] Status check response headers: {json.dumps(dict(response.headers), indent=2)}")

            if response.status_code == 200:
                result = response.json()
                logger.info(f"[For4Payments] Payment status check response: {json.dumps(result, indent=2)}")

                return {
                    'status': result.get('status', 'PENDING'),
                    'pixQrCode': result.get('pixQrCode'),
                    'pixCode': result.get('pixCode')
                }
            elif response.status_code == 404:
                logger.warning(f"[For4Payments] Payment {payment_id} not found")
                return {'status': 'PENDING'}
            else:
                logger.error(f"[For4Payments] Error checking payment status: {response.text}")
                return {'status': 'PENDING'}

        except Exception as e:
            logger.error(f"[For4Payments] Error checking payment status: {str(e)}")
            return {'status': 'PENDING'}


def create_payment_api() -> For4PaymentsAPI:
    """Create and return an instance of For4PaymentsAPI with configuration"""
    secret_key = os.environ.get('FOR4PAYMENTS_SECRET_KEY')
    if not secret_key:
        logger.warning("FOR4PAYMENTS_SECRET_KEY not found in environment, checking if secret needs to be requested")
        raise ValueError("FOR4PAYMENTS_SECRET_KEY is required")
    return For4PaymentsAPI(secret_key)