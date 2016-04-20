from hashlib import md5
from functools import partialmethod
import requests

class ImproperlyConfigured(Exception):
    pass

class PayU:
    defaults = {
        'PAYMENT_URL': "https://stg.api.payulatam.com/payments-api/4.0/service.cgi",
        'QUERY_URL': 'https://stg.api.payulatam.com/reports-api/4.0/service.cgi',
        "API_KEY": None,
        "API_LOGIN": None,
        'ACCOUNT_ID': None,
        'MERCHANT_ID': None,
        'TEST': False,
        'LANG': 'es',
        "VERIFY_SSL": True,
    }

    def __init__(self, **conf):
        self.configure(**conf)

    def configure(self, **conf):
        self.config = {}
        self.config.update(self.defaults)
        for key, value in conf.items():
            self.config[key.upper()] = value

    def get_headers(self):
        return {'Accept': 'application/json'}

    def build_request_base(self, cmd):
        request = {}
        request['test'] = self.config['TEST']
        request['language'] = self.config['LANG']
        request['command'] = cmd
        request['merchant'] = {
            "apiLogin": self.config['API_LOGIN'],
            "apiKey": self.config['API_KEY']
        }
        return request


    def build_signature(self, order, sep='~', algorithm='md5'):
        self.validate_signature(order)
        ref = order.get('referenceCode')
        value = order.get('value')
        currency = order.get('currency')
        msg = sep.join([self.config['API_KEY'],
                        self.config['MERCHANT_ID'],
                        ref,
                        value,
                        currency]).encode('ascii')
        return md5(msg).hexdigest()

    def post(self, request_data, url='PAYMENT_URL'):
        headers = self.get_headers()
        resp = requests.post(self.config.get(url),
                             json=request_data,
                             verify=self.config['VERIFY_SSL'],
                             headers=headers)
        return resp

    def tokenize(self, cc_data):
        self.validate_cc(cc_data)
        cmd = 'CREATE_TOKEN'
        request_data = self.build_request_base(cmd)
        request_data['creditCardToken'] = cc_data
        return self.post(request_data)

    def build_order(self, order):
        order['accountId'] = self.config['ACCOUNT_ID']
        order['signature'] = self.build_signature(order)
        if 'additionalValues' not in order:
            order['additionalValues'] = {
                'TX_VALUE': {
                    'value': order.get('value'),
                    'currency': order.get('currency')
                }
            }

        return order

    def build_transaction(self, order, payment_method, payment_country, **kwargs):
        t = {}
        t['paymentMethod'] = payment_method
        t['paymentCountry'] = payment_country

        if 'credit_card' in kwargs:
            cc = kwargs.get('credit_card')
            self.validate_cc(cc)
            t['creditCard'] = cc
        elif 'credid_card_token' in kwargs:
            t['creditCardTokenId'] = kwargs.get('credit_card_token')

        if 'type' not in 'kwargs':
            t['type'] = 'AUTHORIZATION_AND_CAPTURE'


        # TODO: Support multiple orders in one transaction
        t['order'] = order

        t.update(kwargs)
        return t


    def validate(self, data, fields=[]):
        errors = []
        for field in fields:
            if field not in data:
                errors.append(field)
        if errors:
            raise ImproperlyConfigured('Missing attributes: %s' % ', '.join(errors))


    validate_cc = partialmethod(validate,
                                fields=['payerId',
                                        'name',
                                        'paymentMethod',
                                        'number',
                                        'expirationDate'])

    validate_signature = partialmethod(validate,
                                       fields=['referenceCode',
                                               'value',
                                               'currency'])