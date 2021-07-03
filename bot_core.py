from __future__ import absolute_import, division, print_function, unicode_literals
from mylib.gcp_storage_loader import IS_LOCAL
from .symbols import *


import datetime
import traceback
import pytz

INVESTMENT_TYPE_LONG = 1
INVESTMENT_TYPE_SHORT = 2
INVESTMENT_TYPE_EXIT = 3

ASSET_TYPE_CRYPTO = 1
ASSET_TYPE_STOCK = 2
ASSET_TYPE_INDEX = 3
ASSET_TYPE_UNDEFINED = -1

EVENT_TYPE_NEW_QUOTE = 1
EVENT_TYPE_NEW_FORECAST = 2

BULL = 'BULL'
BEAR = 'BEAR'
ZIGZAG = 'ZIGZAG'


STORAGE_LOADER = None
IS_LOCAL = False


TAKE_PROFIT_POINTS = {
    SMP_SPY + INTERVAL_4HOURS: 1.003,
    NASDAQ_QQQ + INTERVAL_4HOURS: 1.003,
    BTC + INTERVAL_4HOURS: 1.01,
    BTC + INTERVAL_1D: 1.02,
    ETH + INTERVAL_1D: 1.04,
    ETH + INTERVAL_4HOURS: 1.02,
    LTC + INTERVAL_1D: 1.02,
    LTC + INTERVAL_4HOURS: 1.02,
    TWTR + INTERVAL_1D: 1.02,
    TWTR + INTERVAL_4HOURS: 1.01,
    'DEFAULT': 1.01
}


def describe_forecast_bbz(f_0):
  length = len(f_0['forecast'])
  a = 0
  b = int(length / 2)
  c = length
  x = describe_forecast_bbz_from_to(f_0, a, b)
  y = describe_forecast_bbz_from_to(f_0, b+1, c)
  return [x, y], x + '-' + y


def describe_forecast_bbz_from_to(f_0, a, b):
  result = []
  count_p = 0
  count_m = 0
  quote_0 = f_0['last_quote']
  quote_top = f_0['quotes_forecast_top']
  direction_change = 0
  for i in range(a, b):
    if quote_top[i] >= quote_0:
      count_p += 1
    else:
      count_m += 1
    
  if count_p > count_m:
    return('BULL')
  else:
    return('BEAR')


def is_tmz_naive(Date_):
  return (Date_.tzinfo is None or Date_.tzinfo.utcoffset(Date_) is None)


class AlphaBot():

  STATUS_IS_NOT_INVESTED = 0
  STATUS_IS_INVESTED = 1
  STATUS_IS_WAITING_FOR_BETTER_ENTRY = 2


  def __init__(self, symbol, interval, asset_type):
    self.transations = []
    self.current_balance = 100
    self.symbol = symbol
    self.asset_type = asset_type
    self.status = AlphaBot.STATUS_IS_NOT_INVESTED
    self.interval = interval
    searchKey = 'DEFAULT' if not (symbol+interval) in TAKE_PROFIT_POINTS.keys() else (symbol + interval)
    self.TAKE_PROFIT_POINT = TAKE_PROFIT_POINTS[searchKey]
    self.STOP_LOSS_POINT = 1 - (TAKE_PROFIT_POINTS[searchKey] - 1) * 3
    self.event_listeners = []
    if interval not in [INTERVAL_1D, INTERVAL_4HOURS]:
      raise Exception(interval + ' is not supported by AlphaBot')

  def register(self, event_listener):
    self.event_listeners.append(event_listener)

  def notify(self, investment_type, date_0):
    for el in self.event_listeners:
      try:
        if investment_type == INVESTMENT_TYPE_LONG or investment_type == INVESTMENT_TYPE_SHORT:
          el.event_investment_started(self.symbol, self.interval, investment_type, date_0, self.current_balance)
        else:
          el.event_investment_exited(self.symbol, self.interval, date_0, self.current_balance)
          el.event_new_forecast_required(date_0)
      except Exception as E:
        print('ERROR: ', E)
        traceback.print_exc()

  def calculate_recommended_exit(self, date_0, f_0):
    highest_level_1 = max(f_0['level_1'].index(max((f_0['level_1']))), 10)
    if self.interval == INTERVAL_1D:
      recommended_exit = date_0 + datetime.timedelta(days=highest_level_1)
    else:
      recommended_exit = date_0 + datetime.timedelta(hours=highest_level_1 * 4)
    
    return recommended_exit


  def calculate_recommended_half_time(self, date_0):
    highest_level_1 = 5
    if self.interval == INTERVAL_1D:
      recommended_exit = date_0 + datetime.timedelta(days=highest_level_1)
    else:
      recommended_exit = date_0 + datetime.timedelta(hours=highest_level_1 * 4)
    
    return recommended_exit


  def calculate_recommended_wait(self, date_0):
    highest_level_1 = 3
    if self.interval == INTERVAL_1D:
      recommended_exit = date_0 + datetime.timedelta(days=highest_level_1)
    elif self.interval == INTERVAL_4HOURS:
      recommended_exit = date_0 + datetime.timedelta(hours=highest_level_1 * 4)
    
    return recommended_exit


  def do_invest(self, f_0, type_1, type_2):
    true_closings = f_0['true_closings']
    true_dates = f_0['true_dates']
    quote_0 = f_0['last_quote']
    date_0 = f_0['last_date']
    if 'T' in str(date_0):
      # fix the date format
      date_0 = datetime.datetime.strptime(str(date_0).replace('T', ' ')[:19], '%Y-%m-%d %H:%M:%S')

    print()
    print('start of go ', 'long' if type_2 == INVESTMENT_TYPE_LONG else 'short', ' = ', date_0, ' / ', quote_0)


    current_point = 0
    discount_factor = 0

    self.transations.append({
        'quote_0': quote_0,
        'date_0': date_0,
        'type': type_2,
        'recommended_exit': self.calculate_recommended_exit(date_0, f_0),
        'real_exit': None,
        'current_balance': self.current_balance
    })
    self.status = AlphaBot.STATUS_IS_INVESTED
    self.notify(type_2, date_0)
    return


  def check_investment(self, Date_, Close):
    print('check_investment(', self.symbol, ', ', self.interval, ', ', Date_, ', ', Close, ')')
    if self.status == AlphaBot.STATUS_IS_INVESTED:
      last_transaction = self.transations[-1]
      last_transaction_quote_0 = last_transaction['quote_0']
      last_transaction_date_0 = last_transaction['date_0']
      last_transaction_type = last_transaction['type']
      last_transaction_recommended_exit = last_transaction['recommended_exit']
      if Date_ > last_transaction_date_0:
        #print('check_investment | new incomping quote = ', Date_, ' / ', Close, '  <> ', last_transaction_quote_0, ' @ ', last_transaction_date_0)
        #print('current: ', Date_, ' / ', Close, ' ---- last transaction: ', last_transaction_date_0, ' / ', last_transaction_quote_0, ' / ', last_transaction_type, ' -- exit at ', last_transaction_recommended_exit)
        exit_point_reached = False
        if Date_ >= last_transaction_recommended_exit:
          print('RECOMMEDED EXIT POINT!')
          exit_point_reached = True
        is_in_patience_phase = False #= Date_ <= self.calculate_recommended_half_time(last_transaction_date_0)

        loss_gain = Close / last_transaction_quote_0
        factor = loss_gain if last_transaction_type == INVESTMENT_TYPE_LONG else 2 - loss_gain
        current_balance_snapshot = self.current_balance * factor
        
        S = 'L' if last_transaction_type == INVESTMENT_TYPE_LONG else 'S'
        print(S, '\t', last_transaction_quote_0, ' : ',  Close, ' @ ', Date_, ' \t|  factor: ', factor, ', balance: ', current_balance_snapshot, ' // TPP   : ', self.TAKE_PROFIT_POINT, '  - SLP   : ', self.STOP_LOSS_POINT, ' | is in patience phase? ', is_in_patience_phase)
        if (factor > self.TAKE_PROFIT_POINT) or exit_point_reached:
          print('\t\t\tBAM!')
          self.current_balance = current_balance_snapshot
          self.status = AlphaBot.STATUS_IS_NOT_INVESTED
        elif (factor < self.STOP_LOSS_POINT and not is_in_patience_phase) or exit_point_reached:
          print('\t\t\tSHIT!')
          self.current_balance = current_balance_snapshot
          self.status = AlphaBot.STATUS_IS_NOT_INVESTED

        if self.status == AlphaBot.STATUS_IS_NOT_INVESTED:
          print('E X I T')
          # ok. It seems we exited the position
          self.transations[-1]['real_exit'] = Date_
          self.transations[-1]['current_balance'] = self.current_balance
          self.notify(INVESTMENT_TYPE_EXIT, Date_)
      else:
        # the quote is not after investment
        #print('quote ', Date_, ' / ', Close, ' is before investment')
        pass

  def is_in_waiting_phase(self, last_date):
    if len(self.transations) == 0:
      return False
    else:
      return self.calculate_recommended_wait(self.transations[-1]['real_exit']) < last_date


  def do_go_long_short_or_exit(self, forecast_obj):
    print('do_go_long_short_or_exit | ', quick_explain(forecast_obj['last_quote'], forecast_obj['quotes_forecast_top']))
    # initial investment?

    if self.status == AlphaBot.STATUS_IS_NOT_INVESTED:
      #print('investment for ', self.symbol, ' / ', self.interval, ' starting...')
      # decide to go long or short
      f_0 = forecast_obj
      date_0 = f_0['last_date']
      quote_0 = f_0['last_quote']
      dates_1ff = f_0['true_dates']
      quotes_1ff = f_0['true_closings']
      forecast, forecast_text = describe_forecast_bbz(f_0)
      if is_tmz_naive(date_0):
        date_0 = date_0.replace(tzinfo=pytz.utc)
        f_0['last_date'] = date_0
      print('-------------------------')
      print(forecast_text)
      self.do_invest(f_0, INVESTMENT_TYPE_LONG if forecast[0] == BULL else INVESTMENT_TYPE_SHORT, INVESTMENT_TYPE_LONG if forecast[1] == BULL else INVESTMENT_TYPE_SHORT)
    else:
      # already invested...
      print('IGNOrinG ForeCAST... ALREADY INVESTED')
      pass


  def check_investment_event(self, event_type, event_obj):
    print('check_investment_event | ', len(self.transations), ' transactions exist; event_type = ', event_type, ' (', type(event_type), ')')

    if event_type == EVENT_TYPE_NEW_QUOTE and len(self.transations) > 0:
      Close = event_obj['Close']
      Date_ = event_obj['Date_']
      # check if TMZAWARE:
      if not is_tmz_naive(Date_):
        Date_ = Date_.replace(tzinfo=pytz.utc)

      self.check_investment(Date_, Close)
      pass
    elif event_type == EVENT_TYPE_NEW_FORECAST:
      print('\t\tF: ', event_obj['f_0']['last_date'], event_obj['f_0']['last_quote'])
      self.do_go_long_short_or_exit(event_obj['f_0'])
      pass
    elif len(self.transations) == 0:
      print('check_investment_event | no transactions exist yet')
      pass
    else:
      print('UNKNOWN EVENT TYPE: ', event_type)
      pass

def quick_explain(quote_0, X):
  t = ''
  for x in X:
    if x > quote_0:
      t += '+'
    elif x < quote_0:
      t += '-'
    else:
      t += '='
  return t