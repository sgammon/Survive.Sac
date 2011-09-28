''' TMD - Survive Sac '''

import cgi
import urllib
import config
import datetime

import logging

import webapp2 as webapp

from webapp2_extras import jinja2

from google.appengine.ext import db
from google.appengine.ext.webapp.util import run_wsgi_app


class Player(db.Model):
	
	full_name = db.StringProperty()
	email = db.EmailProperty()
	date = db.DateTimeProperty(auto_now_add=True)
	age = db.StringProperty()
	refer = db.StringProperty(multiline=True)
	previous_game = db.BooleanProperty()
	smartphone = db.BooleanProperty()
	paypal = db.StringProperty()


def team_key(team_name=None):

	"""Create datastore key for Team entity with team_name"""
	return db.Key.from_path('Team', team_name or 'default_team')


class TMDHandler(webapp.RequestHandler):
	
	@webapp.cached_property
	def jinja2(self):
		return jinja2.get_jinja2(app=self.app)
		
	def render(self, template, context={}, **kwargs):
		
		if len(kwargs) > 0:
			for k, v in kwargs.items():
				context[k] = v
		
		self.response.write(self.jinja2.render_template(template, **context))


class MainPage(TMDHandler):

	def get(self):
		
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
		
		#players = db.GqlQuery("SELECT * FROM Player WHERE ANCESTOR IS :1 ORDER BY date DESC LIMIT 10", team_key(team_name))
		
		self.render('registration.html', alert=alert, alert_type=alert_type)
		


class Team(TMDHandler):

	def post(self):

		team_name = self.request.get('team_name')
		player = Player(parent=team_key(team_name))
		player.full_name = self.request.get('full_name')
		player.age = self.request.get('age')
		player.email = self.request.get('email')
		player.refer = self.request.get('refer')
		
		logging.info('REQUEST: ' + str(self.request))
		previous_game = self.request.get('previous_game', False)
		
		if previous_game in ['1', 'on', 'yes', 'checked', 'True', True, 1]:
			player.previous_game = True
		else:
			player.previous_game = False
		
		smartphone = self.request.get('smartphone', False)

		if smartphone in ['1', 'on', 'yes', 'checked', 'True', True, 1]:
			player.smartphone = True
		else:
			player.smartphone = False

		paypal = self.request.get('paypal', False)
		if paypal != 'paypal confirmation number' and paypal not in [False, None, 0]:
			player.paypal = self.request.get('paypal')
		else:
			self.redirect('/?' + urllib.urlencode({'fail': 'true', 'reason': 'paypal_invalid'}))

		logging.info('Subscribing player: '+str(player.full_name))
		k = player.put()
		
		if isinstance(k, db.Key):
			self.redirect('/success?' + urllib.urlencode({'full_name': str(player.full_name)}))
		else:
			self.redirect('/?' + urllib.urlencode({'fail': 'true', 'reason': 'unknown'}))
			
			
class Callback(TMDHandler):
	
	def get(self):
		
		full_name = self.request.get('full_name')
		self.render('confirmation.html', fullname=full_name)
		

TMD = webapp.WSGIApplication([
	('/', MainPage),
	('/create', Team),
	('/success', Callback)
	], debug=True, config=config.config)
	
	
def main():
	run_wsgi_app(TMD)

if __name__ == '__main__':
	main()