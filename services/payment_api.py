import os
import json
import logging
import re
from typing import Dict, Any
from urllib.parse import urljoin
import uuid
import pprint

import requests
from flask import current_app

logger = logging.getLogger(__name__)

class For4PaymentsAPI:

    def __init__(self, secret_key: str = None):
        self.API_URL = "https://app.for4payments.com.br/api/transaction"  # Updated API URL
        self.secret_key = secret_key or os.environ.get('FOR4PAYMENTS_SECRET_KEY')
        if not self.secret_key:
            raise ValueError("For4Payments secret key is required")

        # Log initialization with masked key
        masked_key = self.secret_key[:8] + "..." if self.secret_key else "None"
        logger.info(f"[For4Payments] Initializing with key: {masked_key}")

    def _get_headers(self) -> Dict[str, str]:
        """Get headers with proper authorization"""
        return {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Authorization': f"Bearer {self.secret_key}"  # Added authorization header
        }

    def _format_phone(self, phone: str) -> str:
        """Format phone number to match API requirements"""
        # Remove all non-digits
        clean_phone = ''.join(filter(str.isdigit, phone))

        # Remove country code if present
        if clean_phone.startswith('55'):
            clean_phone = clean_phone[2:]

        # Validate the phone number format
        if not re.match(r'^\d{8,12}$', clean_phone):
            raise ValueError("Phone number must be between 8 and 12 digits")

        return f"55{clean_phone}"  # Add country code back

    def create_pix_payment(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new PIX payment"""
        transaction_id = str(uuid.uuid4())
        logger.info(f"\n[For4Payments][{transaction_id}] Starting new payment transaction")

        try:
            # Convert amount to cents
            amount_cents = int(float(data['amount']) * 100)

            # Clean CPF
            clean_cpf = ''.join(filter(str.isdigit, data['cpf']))

            # Format phone according to API requirements
            formatted_phone = self._format_phone(data['phone'])

            payment_data = {
                'amount': amount_cents,
                'cpf': clean_cpf,
                'email': data['email'],
                'items': [{
                    'quantity': 1,
                    'tangible': False,
                    'title': 'tarifa transacional',
                    'unitPrice': amount_cents
                }],
                'name': data['name'],
                'paymentMethod': 'PIX',
                'phone': formatted_phone
            }

            url = f"{self.API_URL}.purchase"
            headers = self._get_headers()

            # Log request details before making the call
            self._log_request_response(
                transaction_id=transaction_id,
                method="POST",
                url=url,
                headers=headers,
                request_data=payment_data
            )

            # Make the request
            response = requests.post(url, headers=headers, json=payment_data)

            # Log complete response details
            self._log_request_response(
                transaction_id=transaction_id,
                method="POST",
                url=url,
                headers=headers,
                request_data=payment_data,
                response=response
            )

            if response.status_code != 200:
                error_msg = f"Payment API error ({response.status_code}): {response.text}"
                logger.error(f"[For4Payments][{transaction_id}] {error_msg}")
                raise ValueError(error_msg)

            result = response.json()
            return {
                'id': result['id'],
                'pixCode': result['pixCode'],
                'pixQrCode': result['pixQrCode'],
                'expiresAt': result.get('expiresAt'),
                'status': result.get('status', 'PENDING')
            }

        except Exception as e:
            logger.error(f"[For4Payments][{transaction_id}] Error creating payment: {str(e)}")
            raise

    def check_payment_status(self, payment_id: str) -> Dict[str, str]:
        """Check the status of a payment"""
        transaction_id = str(uuid.uuid4())
        try:
            url = f"{self.API_URL}.status/{payment_id}"
            headers = self._get_headers()

            # Log request details
            self._log_request_response(
                transaction_id=transaction_id,
                method="GET",
                url=url,
                headers=headers,
                request_data={}
            )

            response = requests.get(url, headers=headers)

            # Log response
            self._log_request_response(
                transaction_id=transaction_id,
                method="GET",
                url=url,
                headers=headers,
                request_data={},
                response=response
            )

            if response.status_code == 200:
                result = response.json()
                status = result.get('status', 'PENDING').upper()
                logger.info(f"[For4Payments][{transaction_id}] Payment status: {status}")
                return {
                    'status': status,
                    'pixQrCode': result.get('pixQrCode'),
                    'pixCode': result.get('pixCode')
                }
            else:
                logger.error(f"[For4Payments][{transaction_id}] Error checking payment status: {response.text}")
                return {'status': 'PENDING'}

        except Exception as e:
            logger.error(f"[For4Payments][{transaction_id}] Error checking payment status: {str(e)}")
            return {'status': 'PENDING'}

    def _log_request_response(self, transaction_id: str, method: str, url: str, 
                            headers: Dict, request_data: Dict, response: requests.Response = None):
        """Log detailed request and response information"""
        # Log Request
        logger.info(f"\n{'='*80}\n[For4Payments][{transaction_id}] REQUEST DETAILS\n{'='*80}")
        logger.info(f"Method: {method}")
        logger.info(f"URL: {url}")

        # Mask authorization header if present
        safe_headers = headers.copy()
        if 'Authorization' in safe_headers:
            safe_headers['Authorization'] = "Bearer ***"

        logger.info("Headers:")
        logger.info(pprint.pformat(safe_headers, indent=2))

        if request_data:
            # Log request body with sensitive data masked
            safe_request = {
                **request_data,
                'cpf': f"{request_data.get('cpf', '')[:3]}****{request_data.get('cpf', '')[-2:]}" if 'cpf' in request_data else None,
                'phone': f"****{request_data.get('phone', '')[-4:]}" if 'phone' in request_data else None
            }
            logger.info("Request Body:")
            logger.info(pprint.pformat(safe_request, indent=2))

        # Log Response if available
        if response:
            logger.info(f"\n{'='*80}\n[For4Payments][{transaction_id}] RESPONSE DETAILS\n{'='*80}")
            logger.info(f"Status Code: {response.status_code}")
            logger.info("Response Headers:")
            logger.info(pprint.pformat(dict(response.headers), indent=2))
            logger.info("Raw Response Body:")
            logger.info(response.text)

        logger.info(f"{'='*80}\n")

def create_payment_api() -> For4PaymentsAPI:
    """Create and return an instance of For4PaymentsAPI with configuration"""
    secret_key = os.environ.get('FOR4PAYMENTS_SECRET_KEY')
    if not secret_key:
        logger.warning("FOR4PAYMENTS_SECRET_KEY not found in environment")
        raise ValueError("FOR4PAYMENTS_SECRET_KEY is required")
    return For4PaymentsAPI(secret_key=secret_key)