import json
import hashlib
from flask import current_app, request
from typing import Optional, Dict, Any

class FacebookPixel:
    def __init__(self, pixel_id: str):
        self.pixel_id = pixel_id

    def _hash_data(self, data: str) -> str:
        """Hash data using SHA256"""
        return hashlib.sha256(data.lower().strip().encode()).hexdigest()

    def _get_base_script(self) -> str:
        """Returns the base Facebook Pixel initialization script"""
        return f'''
        <!-- Facebook Pixel Code -->
        <script>
            !function(f,b,e,v,n,t,s)
            {{if(f.fbq)return;n=f.fbq=function(){{n.callMethod?
            n.callMethod.apply(n,arguments):n.queue.push(arguments)}};
            if(!f._fbq)f._fbq=n;n.push=n;n.loaded=!0;n.version='2.0';
            n.queue=[];t=b.createElement(e);t.async=!0;
            t.src=v;s=b.getElementsByTagName(e)[0];
            s.parentNode.insertBefore(t,s)}}(window, document,'script',
            'https://connect.facebook.net/en_US/fbevents.js');
            fbq('init', '{self.pixel_id}');
            fbq('track', 'PageView');
        </script>
        <noscript>
            <img height="1" width="1" style="display:none"
                src="https://www.facebook.com/tr?id={self.pixel_id}&ev=PageView&noscript=1"/>
        </noscript>
        <!-- End Facebook Pixel Code -->
        '''

    def get_purchase_event_script(self, 
                                value: float,
                                currency: str = 'BRL',
                                content_type: str = 'product',
                                content_ids: Optional[list] = None,
                                transaction_id: Optional[str] = None,
                                user_data: Optional[Dict[str, str]] = None) -> str:
        """Returns the Facebook Pixel purchase event script"""
        params = {
            'value': value,
            'currency': currency,
            'content_type': content_type
        }

        if content_ids:
            params['content_ids'] = content_ids

        if transaction_id:
            params['transaction_id'] = transaction_id

        if user_data:
            # Hash user data
            user_params = {}
            if 'email' in user_data:
                user_params['em'] = self._hash_data(user_data['email'])
            if 'phone' in user_data:
                # Remove non-digits and then hash
                clean_phone = ''.join(filter(str.isdigit, user_data['phone']))
                user_params['ph'] = self._hash_data(clean_phone)
            if 'name' in user_data:
                names = user_data['name'].split(' ')
                if names:
                    user_params['fn'] = self._hash_data(names[0])
                    if len(names) > 1:
                        user_params['ln'] = self._hash_data(' '.join(names[1:]))

            params.update(user_params)

        return f'''
        <script>
            fbq('track', 'Purchase', {json.dumps(params)});
        </script>
        '''

    def inject_base_code(self, response):
        """Inject Facebook Pixel base code into HTML response"""
        if response.content_type.startswith('text/html'):
            response.direct_passthrough = False
            html = response.get_data(as_text=True)
            if '</head>' in html:
                pixel_code = self._get_base_script()
                html = html.replace('</head>', f'{pixel_code}</head>')
                response.set_data(html)
        return response