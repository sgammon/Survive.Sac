''' TMD - Survive Sac '''

import os
import cgi
import hmac
import base64
import urllib
import config
import random
import string
import hashlib
import slimmer
import datetime

from xml.dom import minidom

import logging

import webapp2 as webapp

try:
	import json
except ImportError:
	try:
		import simplejson as json
	except ImportError:
		from django.utils import simplejson as json

from webapp2_extras import routes
from webapp2_extras import jinja2
from webapp2_extras import sessions

from google.appengine.ext import db
from google.appengine.api import mail
from google.appengine.api import users
from google.appengine.api import channel
from google.appengine.api import urlfetch
from google.appengine.api import taskqueue
from google.appengine.ext.webapp.util import run_wsgi_app


class Player(db.Model):
	
	full_name = db.StringProperty()
	email = db.EmailProperty()
	date = db.DateTimeProperty(auto_now_add=True)
	age = db.StringProperty()
	refer = db.StringProperty(multiline=True)
	previous_game = db.BooleanProperty()
	smartphone = db.BooleanProperty()
	gender = db.StringProperty(choices=['male', 'female'])
	fb = db.BooleanProperty(default=False)
	fb_id = db.StringProperty()
	fb_username = db.StringProperty()
	paid = db.BooleanProperty(default=False)
	checkout_order_id = db.StringProperty()

	## Merchandising !!
	ordered_map = db.BooleanProperty(default=False)
	ordered_rations = db.BooleanProperty(default=False)
	
	
class CheckoutOrder(db.Model):
	
	order_id = db.StringProperty()
	status = db.StringProperty(choices=['queued', 'charged', 'complete'], default='queued')
	player = db.ReferenceProperty(Player, collection_name='checkout_orders')
	serial_number = db.StringProperty()


def team_key(team_name=None):

	"""Create datastore key for Team entity with team_name"""
	return db.Key.from_path('Team', team_name or 'default_team')


class TMDHandler(webapp.RequestHandler):
	
	@webapp.cached_property
	def jinja2(self):
		return jinja2.get_jinja2(app=self.app)
		
	@webapp.cached_property
	def session(self):
		return self.session_store.get_session()
		
	def dispatch(self):
		# Resolve session store
		self.session_store = sessions.get_store(request=self.request)
		
		try:
			# Dispatch request
			webapp.RequestHandler.dispatch(self)
		finally:
			# Save session after request is dispatched
			self.session_store.save_sessions(self.response)
	
	def generateSession(self):
		character_pool = string.ascii_letters + string.digits
		self.session['sid'] = '-'.join([reduce(lambda x, y: x+y, [random.choice(character_pool) for i in range(0, 8)]) for igroup in range(0, 8)])
		self.session['token'] = hashlib.sha256(self.session['sid']+os.environ['REMOTE_ADDR']).hexdigest()
		self.session['addr'] = os.environ['REMOTE_ADDR']
		self.session['timestamp'] = datetime.datetime.now().isoformat()
		
	def render(self, template, context={}, **kwargs):
		
		baseContext = {
			
			'link': self.url_for,
			'user': {
				'is_admin': users.is_current_user_admin()
			}
		
		}
		
		if len(kwargs) > 0:
			for k, v in kwargs.items():
				context[k] = v
				
		for k, v in baseContext.items():
			context[k] = v
			
		#self.response.write(slimmer.html_slimmer(self.jinja2.render_template(template, **context)))
		self.response.write(self.jinja2.render_template(template, **context))


class MainPage(TMDHandler):

	def get(self):

		if 'sid' not in self.session:
			self.generateSession()
					
		fail = self.request.get('fail', False)
		success = self.request.get('success', False)

		alert = False
		alert_type = False

		if any([fail, success]):

			if fail:
				alert_type = 'fail'
			else:
				alert_type = 'success'
				
			if fail is not False:
				fail = self.request.get('reason')
				if fail == 'unknown':
					alert = 'An unknown error occurred. Please try again later.'
				elif fail == 'paypal_invalid':
					alert = 'The PayPal verification you provided was invalid. Please try again.'
			elif success is not False:
				alert = 'Success! You have been registered.'
	
				
		team_name = self.request.get('team_name')
		checkout_cfg = config.config.get('google.checkout')
		if checkout_cfg['sandbox'] == True:
			sandbox = 'true'
			mid = checkout_cfg['sandbox_mid']
		else:
			sandbox = 'false'
			mid = checkout_cfg['mid']
		
		session_id = urllib.quote(str(base64.b64encode(self.session['sid'])))
		session_token = self.session['token']
		session_csrf = hashlib.sha512(self.session['sid']+self.session['token']).hexdigest()
		self.render('registration.html', alert=alert, alert_type=alert_type, step=1, sandbox=sandbox, checkout_mid=mid, sid=session_id, token=session_token, csrf=session_csrf, environ=os.environ)
		
	def post(self):
		logging.info('POST RECEIVED AT LANDING: '+str(self.request))
		self.get()
		


class RegisterPlayerAJAX(TMDHandler):

	def post(self):

		sid = self.request.get('sid')
		token = self.request.get('token')
		csrf = self.request.get('csrf')
		name = self.request.get('name')
		email = self.request.get('email')
		age = self.request.get('age')
		fb_profile = self.request.get('fb_profile')
		
		if fb_profile == 'true':
			fb = json.loads(self.request.get('fb'))
		else:
			fb = None
		
		if Player.get_by_key_name(email) is None:
			pass
			
		if True:
		
			p = Player(key_name=email)
			p.full_name = name
			p.email = email
			p.age = age
			if fb_profile == 'true':
				p.fb = True
				p.fb_id = fb['id']
				p.fb_username = fb['username']
				p.gender = fb['gender']
				
			p_key = p.put()
			
			logging.info('PUT PLAYER: '+str(p_key))
			success = {'status': 'success', 'player': {'key': str(p_key)}, 'token': self.request.get('token')}
			
			logging.info('RETURNING SUCCESS: '+json.dumps(success))
			self.response.write(json.dumps(success))
				
		else:

			logging.info('PLAYER ALREADY EXISTS.')
			error = {'status': 'error', 'error': {'code': 'player_already_exists', 'message': 'A player has already registered with that email address.'}}

			logging.info('RETURNING ERROR: '+json.dumps(error))
			self.response.write(json.dumps(error))
		

class Checkout(TMDHandler):
	
	def post(self):

		logging.info('PREPARE CHECKOUT REQUEST!')

		rations_package = self.request.get('rations_package', 'false')
		game_map = self.request.get('game_map', 'false')
		user_key = self.request.get('user_key')
		
		logging.info('USERKEY: '+str(user_key))
		
		context = {}
		
		subtotal = 5
		if rations_package == 'true':
			subtotal += 5
			context['rations_package'] = True
		if game_map == 'true':
			subtotal += 3
			context['game_map'] = True
			
		if config.debug:
			continue_baseurl = 'http://localhost:8080/success?'
		else:
			continue_baseurl = 'https://survive-sac.appspot.com/success?'
			
		context['sid'] = base64.b64encode(self.session['sid'])
		context['token'] = self.session['token']
		context['user_key'] = user_key
			
		context['continue_url'] = continue_baseurl+urllib.urlencode({'tmd_session': json.dumps({'sid': base64.b64encode(self.session['sid']), 'token': self.session['token'], 'u': user_key})})
		api_request = self.jinja2.render_template('snippets/checkout_api_request.xml', **context)
		
		logging.info('GENERATED API REQUEST: '+str(api_request))
		
		if config.config['google.checkout']['sandbox'] is True:
			hmac_sig = hmac.new(config.config['google.checkout']['sandbox_mkey'], api_request, hashlib.sha1)
		else:
			hmac_sig = hmac.new(config.config['google.checkout']['mkey'], api_request, hashlib.sha1)
			
		b64_hmac_sig = base64.b64encode(hmac_sig.digest())
		b64_api_request = base64.b64encode(api_request)
		checkout_request = {'hmac': str(b64_hmac_sig), 'request': str(b64_api_request)}
		
		self.response.write(json.dumps(checkout_request))
		
	
			
class CheckoutCallback(TMDHandler):
	
	def post(self):
		
		m = minidom.parseString(self.request.body)

		# Get Session ID, Token, & User Key
		session_id = m.getElementsByTagName('session-id')[0].childNodes[0].data
		session_token = m.getElementsByTagName('session-token')[0].childNodes[0].data
		user_key = m.getElementsByTagName('user-key')[0].childNodes[0].data
		order_num = m.getElementsByTagName('google-order-number')[0].childNodes[0].data
		
		k = db.Key(user_key)
		player = db.get(k)
		player.paid = True
		p_key = player.put()
		
		o = CheckoutOrder(player, key_name=order_num)
		o.order_id = order_num
		o.status = 'queued'
		o.player = player
		o_key = o.put()
		
		notify_page = taskqueue.Task(method='GET', url='/_notifySuccess', params={'token': str(session_token)}, countdown=5)
		notify_page.add('notify')
		
		confirmation_email = taskqueue.Task(name=hashlib.md5(player.email).hexdigest(), method='GET', url='/_sendConfirmationEmail', params={'ukey': str(p_key), 'okey': str(o_key)})
		confirmation_email.add('mail')
		
		self.response.out.write('OK')


class Success(TMDHandler):

	def get(self):

		tmd_session = json.loads(self.request.get('tmd_session'))
		self.render('confirmation2.html', livetoken=channel.create_channel(tmd_session['token']))
		
		
class NotifyClientOfSuccess(TMDHandler):
	
	def get(self):
		session_token = self.request.get('token')
		logging.info('Session token: '+str(session_token))
		channel.send_message(session_token, json.dumps({'status': 'success', 'activated': True}))
		
		
class SendSuccessEmail(TMDHandler):
	
	def get(self):
		
		user_key = self.request.get('ukey')
		order_key = self.request.get('okey')
		
		try:
			user = db.get(db.Key(user_key))
			order = db.get(db.Key(order_key))
		except Exception, e:
			logging.error('Error pulling user or order: '+str(e))
			raise
		
		else:
			logging.info('EMAIL NOTIFICATION')
			logging.info('user: '+str(user)+' at key '+str(user_key))
			logging.info('order: '+str(order)+' at key '+str(order_key))
		
			confirmation_email = mail.EmailMessage(
			
				to=user.full_name+' <'+user.email+'>',
				sender='Notifier Kitteh <robot.kitty@providenceclarity.com>',
				subject='Confirming your SurviveSac ticket order',
				html=self.jinja2.render_template('snippets/confirmation_email.html', **{'user': user, 'order': order})
		
			)
		
			logging.info('confirmation_email: '+str(confirmation_email))
			
			try:
				confirmation_email.send()
			except Exception, e:
				logging.error('Error sending confirmation email: '+str(e))
				raise
		
		
class Info(TMDHandler):
	
	def get(self):
		
		self.render('info.html')
		
		
class FBPageTab(TMDHandler):
	
	def get(self):
		return None
		
		
class FBApp(TMDHandler):
	
	def get(self):
		return None
		

TMD = webapp.WSGIApplication([
	routes.HandlerPrefixRoute('teammacdown.',[
		webapp.Route('/', name='landing', handler='MainPage'),
		webapp.Route('/success', name='checkout_callback', handler='Success'),
		webapp.Route('/checkout', name='checkout', handler='Checkout'),
		webapp.Route('/_register', name='create_player', handler='RegisterPlayerAJAX'),		
		webapp.Route('/_callback', name='checkout_callback', handler='CheckoutCallback'),
		webapp.Route('/info', name='info', handler='Info'),
		webapp.Route('/_notifySuccess', name='notify-success', handler='NotifyClientOfSuccess'),
		webapp.Route('/_fb/pagetab', name='fb-pagetab', handler='MainPage'),
		webapp.Route('/_fb/app.*', name='fb-app', handler='MainPage'),
		webapp.Route('/_sendConfirmationEmail', name='send-confirmation', handler='SendSuccessEmail')
	])
], debug=True, config=config.config)
	
	
def main():
	run_wsgi_app(TMD)

if __name__ == '__main__':
	main()