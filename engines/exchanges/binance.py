'''
    All trades have a 0.25% commission. -> real case it is 0.250626606% so use 0.26% for calculation instead

'''

from mod_imports import *
from operator import itemgetter

class ExchangeEngine(ExchangeEngineBase):
    def __init__(self):
        self.API_URL = 'https://api.binance.com/api'
        self.apiVersion = 'v1'
        self.privateApiVersion = 'v3'

        self.sleepTime = 5
        self.feeRatio = 0.001
        self.async = True     
                  
    def _generate_signature(self, data):

        ordered_data = self._order_params(data)
        query_string = '&'.join(["{}={}".format(d[0], d[1]) for d in ordered_data])
        m = hmac.new(self.key['private'].encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256)
        return m.hexdigest()

    def _order_params(self, data):
        """Convert params to list with signature as last element

        :param data:
        :return:

        """
        has_signature = False
        params = []
        for key, value in data.items():
            if key == 'signature':
                has_signature = True
            else:
                params.append((key, value))
        # sort parameters by key
        params.sort(key=itemgetter(0))
        if has_signature:
            params.append(('signature', data['signature']))
        return params        

    def _send_request(self, command, httpMethod, signed, params={}, hook=None):          
        
        v = self.privateApiVersion if signed else self.apiVersion
        url = self.API_URL + '/' + v + '/' + command        
        
        if httpMethod == "GET":
            R = grequests.get
        elif httpMethod == "POST":
            R = grequests.post       
        
        args = {'data': params}

        if signed:
            url_time = self.API_URL + '/' + self.apiVersion + '/time'
            response = grequests.map([grequests.get(url_time)])[0].json()
            server_time = response['serverTime']

            args['headers'] = {'Accept': 'application/json',
                                'User-Agent': 'binance/python',
                                'X-MBX-APIKEY': self.key['public']}

            timestamp = server_time

            signature = self._generate_signature({'timestamp' : timestamp, 'recvWindow': 10000000})
            url = url + '?recvWindow=10000000&signature={}&timestamp={}'.format(signature, timestamp)  

        #print ('REQUEST URL: %s' % url)

        if hook:
            args['hooks'] = dict(response=hook)
            
        req = R(url, **args)
        
        if self.async:
            return req
        else:
            response = grequests.map([req])[0].json()
            #print ('msg: {}, code: {} '.format(response['msg'], response['code']))
            
            if 'error' in response:
                print response
            return response
    '''
        return in r.parsed, showing all and required tickers
        {
            'ETH': 0.005,
            'OMG': 0
        }
    '''    


    def get_balance(self, tickers=[]):
        return self._send_request('account', 'GET', True, {}, [self.hook_getBalance(tickers=tickers)])
    
    def hook_getBalance(self, *factory_args, **factory_kwargs):
        def res_hook(r, *r_args, **r_kwargs):
            json = r.json()

            r.parsed = {}
            
            if factory_kwargs['tickers']:
                json['balances'] = filter(lambda ticker: ticker['asset'].upper() in factory_kwargs['tickers'], json['balances'])

            for ticker in json['balances']:
                r.parsed[ticker['asset'].upper()] = float(ticker['free'])
                                  
        return res_hook    
    
    '''
        return USDT in r.parsed
        {
            'BTC': 18000    
        }
    '''       
    def get_ticker_lastPrice(self, ticker):
         return self._send_request('ticker/price?symbol={0}USDT'.format(ticker), 'GET', False, {}, 
                        [self.hook_lastPrice(ticker=ticker)])

    def hook_lastPrice(self, *factory_args, **factory_kwargs):
        def res_hook(r, *r_args, **r_kwargs):
            json = r.json()

            r.parsed = {}
            r.parsed[factory_kwargs['ticker']] = json['price']      
                                  
        return res_hook    

    '''
        return in r.parsed
        {
            'bid': {
                'price': 0.02202,
                'amount': 1103.5148
            },
            'ask': {
                'price': 0.02400,
                'amount': 103.2
            },           
        }
    '''       
    def get_ticker_orderBook_innermost(self, ticker):
        return self._send_request('depth?symbol={}&limit=5'.format(ticker), 'GET', {}, False, self.hook_orderBook)     
     
    def hook_orderBook(self, r, *r_args, **r_kwargs):
        json = r.json()
        #print json
        r.parsed = {
                    'bid':  {
                             'price': float(json['bids'][0][0]),
                             'amount': float(json['bids'][0][1])
                            },
                    'ask':  {
                             'price': float(json['asks'][0][0]),
                             'amount': float(json['asks'][0][1])
                            }
                    }    




    '''
        return in r.parsed
        [
            {
                'orderId': 1242424
            }
        ]
    '''           
    def get_open_order(self):
        return self._send_request('market/getopenorders', 'GET', {}, self.hook_openOrder)
    
    def hook_openOrder(self, r, *r_args, **r_kwargs):
        json = r.json()
        r.parsed = []
        for order in json['result']:
            r.parsed.append({'orderId': str(order['OrderUuid']), 'created': order['Opened']})

        
    '''
        ticker: 'ETH-ETC'
        action: 'bid' or 'ask'
        amount: 700
        price: 0.2
    '''
    def place_order(self, ticker, action, amount, price):
        action = 'buy' if action == 'bid' else 'sell'
        if action == 'buy':
            cmd = 'market/buylimit?market={0}&quantity={1}&rate={2}'.format(ticker, amount, price)
        else:
            cmd = 'market/selllimit?market={0}&quantity={1}&rate={2}'.format(ticker, amount, price)
        return self._send_request(cmd, 'GET')    
    
    def cancel_order(self, orderID):
        return self._send_request('market/cancel?uuid={0}'.format(orderID), 'GET')
    
    def withdraw(self, ticker, amount, address):
        return self._send_request('account/withdraw?currency={0}&quantity={1}&address={2}'.format(ticker, amount, address), 'GET')
    
    
if __name__ == "__main__":
    engine = ExchangeEngine()
    engine.load_key('../../keys/bittrex.key')
    # for res in grequests.map([engine.get_ticker_orderBook_innermost('ETH-OMG')]):
    #     print res.parsed
    #     pass
    for res in grequests.map([engine.get_ticker_lastPrice('LTC')]):
        print res.parsed
        pass    
    #print engine.get_ticker_orderBook('ETH-OMG')
    #print engine.parseTickerData(engine.get_ticker_history('XRPUSD'))
    #print engine.place_order('ETH-OMG', 'bid', 10, 0.01)
    #print engine.withdraw('ETH', 500, '0x54A82261bAAc1357069E23d953F8dbC8BD2A54F4')
    #print engine.get_open_order()
    #print engine.cancel_order('9faa6b5b-6709-4435-aec8-fe96f1fa32bb')