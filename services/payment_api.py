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
        self.API_URL = "https://app.for4payments.com.br/api/v1"  # Fixed base URL
        self.secret_key = secret_key or os.environ.get('FOR4PAYMENTS_SECRET_KEY')
        self.test_mode = os.environ.get('TEST_MODE', 'false').lower() == 'true'
        if not self.secret_key:
            raise ValueError("For4Payments secret key is required")

        # Log initialization with masked key
        masked_key = self.secret_key[:8] + "..." if self.secret_key else "None"
        logger.info(f"[For4Payments] Initializing with key: {masked_key}")
        if self.test_mode:
            logger.info("[For4Payments] Running in TEST MODE - payments will be auto-approved")

    def _get_headers(self) -> Dict[str, str]:
        """Get headers with proper authorization"""
        return {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Authorization': f'{self.secret_key}'
        }

    def _format_phone(self, phone: str) -> str:
        """Format phone number to match API requirements (8-12 digits)"""
        # Remove all non-digits
        clean_phone = ''.join(filter(str.isdigit, phone))

        # Remove country code if present
        if clean_phone.startswith('55'):
            clean_phone = clean_phone[2:]

        # Validate the phone number format
        if not re.match(r'^\d{8,12}$', clean_phone):
            raise ValueError("Phone number must be between 8 and 12 digits")

        return clean_phone

    def _log_request_response(self, transaction_id: str, method: str, url: str, 
                            headers: Dict, request_data: Dict, response: requests.Response):
        """Log detailed request and response information"""
        logger.info(f"\n{'='*80}\n[For4Payments][{transaction_id}] REQUEST DETAILS\n{'='*80}")
        logger.info(f"Method: {method}")
        logger.info(f"URL: {url}")
        logger.info("Headers:")
        logger.info(pprint.pformat(dict(headers), indent=2))

        # Log request body with sensitive data masked
        safe_request = {
            **request_data,
            'cpf': f"{request_data.get('cpf', '')[:3]}****{request_data.get('cpf', '')[-2:]}" if 'cpf' in request_data else None,
            'phone': f"****{request_data.get('phone', '')[-4:]}" if 'phone' in request_data else None
        }
        logger.info("Request Body:")
        logger.info(pprint.pformat(safe_request, indent=2))

        logger.info(f"\n{'='*80}\n[For4Payments][{transaction_id}] RESPONSE DETAILS\n{'='*80}")
        logger.info(f"Status Code: {response.status_code}")
        logger.info("Response Headers:")
        logger.info(pprint.pformat(dict(response.headers), indent=2))

        try:
            response_text = response.text
            logger.info("Raw Response Body:")
            logger.info(response_text)

            if response.headers.get('content-type', '').startswith('application/json'):
                response_body = response.json()
                logger.info("Parsed JSON Response:")
                logger.info(pprint.pformat(response_body, indent=2))
        except Exception as e:
            logger.error(f"Error processing response: {str(e)}")

    def create_pix_payment(self, data: Dict[str, Any]) -> Dict[str, Any]:
        transaction_id = str(uuid.uuid4())
        try:
            logger.info(f"\n[For4Payments][{transaction_id}] Starting new payment transaction")

            # If in test mode, return auto-approved payment
            if self.test_mode:
                logger.info(f"[For4Payments][{transaction_id}] TEST MODE: Auto-approving payment")
                return {
                    'id': transaction_id,
                    'pixCode': 'TEST_MODE_PIX_CODE',
                    'pixQrCode': 'https://upload.wikimedia.org/wikipedia/commons/d/d0/QR_code_for_mobile_English_Wikipedia.svg',
                    'expiresAt': None,
                    'status': 'completed'
                }

            # Convert amount to cents
            amount_cents = int(float(data['amount']) * 100)

            # Clean CPF
            clean_cpf = ''.join(filter(str.isdigit, data['cpf']))

            # Format phone according to API requirements
            formatted_phone = self._format_phone(data['phone'])

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

            url = f"{self.API_URL}/transaction.purchase"
            headers = self._get_headers()

            # Make the request with token as query parameter
            response = requests.post(
                url,
                headers=headers,
                json=payment_data,
                params={'token': self.secret_key}
            )

            # Log complete request and response details
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
                'status': result.get('status', 'pending')
            }

        except Exception as e:
            logger.error(f"[For4Payments][{transaction_id}] Error creating payment: {str(e)}")
            raise

    def check_payment_status(self, payment_id: str) -> Dict[str, str]:
        """Check the status of a payment"""
        transaction_id = str(uuid.uuid4())

        # If in test mode, always return completed
        if self.test_mode:
            logger.info(f"[For4Payments][{transaction_id}] TEST MODE: Auto-completing payment")
            return {'status': 'completed'}

        try:
            url = f"{self.API_URL}/transaction.getPayment"
            headers = self._get_headers()

            response = requests.get(
                url, 
                headers=headers, 
                params={
                    'id': payment_id,
                    'token': self.secret_key
                }
            )

            # Log complete request and response details
            self._log_request_response(
                transaction_id=transaction_id,
                method="GET",
                url=f"{url}?id={payment_id}",
                headers=headers,
                request_data={},
                response=response
            )

            if response.status_code == 200:
                result = response.json()
                status = result.get('status', 'PENDING').lower()

                # Map API status to our status
                if status in ['paid', 'completed', 'approved']:
                    return {'status': 'completed'}
                elif status in ['cancelled', 'failed', 'refused']:
                    return {'status': 'failed'}
                else:
                    return {
                        'status': 'pending',
                        'pixQrCode': result.get('pixQrCode'),
                        'pixCode': result.get('pixCode')
                    }
            elif response.status_code == 404:
                logger.warning(f"[For4Payments][{transaction_id}] Payment {payment_id} not found")
                return {'status': 'pending'}
            else:
                logger.error(f"[For4Payments][{transaction_id}] Error checking payment status: {response.text}")
                return {'status': 'pending'}

        except Exception as e:
            logger.error(f"[For4Payments][{transaction_id}] Error checking payment status: {str(e)}")
            return {'status': 'pending'}


def create_payment_api() -> For4PaymentsAPI:
    """Create and return an instance of For4PaymentsAPI with configuration"""
    secret_key = os.environ.get('FOR4PAYMENTS_SECRET_KEY')
    if not secret_key:
        logger.warning("FOR4PAYMENTS_SECRET_KEY not found in environment, checking if secret needs to be requested")
        raise ValueError("FOR4PAYMENTS_SECRET_KEY is required")
    return For4PaymentsAPI(secret_key)