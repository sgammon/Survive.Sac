''' TMD - Survive Sac '''

import cgi
import urllib
import datetime

import logging

import webapp2 as webapp

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


class MainPage(webapp.RequestHandler):

	def get(self):
		
		self.response.write("""
<html>
	<head>
		<title>Register to play Survive Sac 2011</title>
		<link rel="stylesheet" type="text/css" href="http://west-us.cdn.static.labs.momentum.io/style/survive-sac-v1.css" />
		<script src="https://ajax.googleapis.com/ajax/libs/jquery/1.6.4/jquery.min.js" type="text/javascript"></script>
	</head>
	<body>""")
	
		fail = self.request.get('fail', False)
		success = self.request.get('success', False)

		if any([fail, success]):

			if fail:
				alert_type = 'fail'
			else:
				alert_type = 'success'
				
			self.response.write("""
				<div id='alert' class='%s'><p>
			""" % alert_type)

			if fail is not False:
				fail = self.request.get('reason')
				if fail == 'unknown':
					self.response.write('An unknown error occurred. Please try again later.')
				elif fail == 'paypal_invalid':
					self.response.write('The PayPal verification you provided was invalid. Please try again.')
			elif success is not False:
				self.response.write('Success! You have been registered.')
	
			self.response.write("""
				</p></div>
			""")
	
		self.response.write("""<div id="wrapper">
			<h1>REGISTER</h1>""")
			
		team_name = self.request.get('team_name')
		
		players = db.GqlQuery("SELECT * FROM Player WHERE ANCESTOR IS :1 ORDER BY date DESC LIMIT 10", team_key(team_name))
		
		self.response.write("""
			<form action="/create?%s" method="post">
				<div><input type="text" name="full_name" placeholder="name" value='name'/></div>
				<div><input type="text" name="email" placeholder="email" value='email' /></div>
				<div><input type="text" name="age" placeholder="age" value='age' /></div>
				<div><input type="checkbox" class="check" name="previous_game" id="previous_game"><label for="previous_game">did you play last year?</label></div>
				<div><input type="checkbox" class="check" name="smartphone" id="smartphone"><label for="smartphone">do you have a smartphone?</label></div>
				<div><input type="text" name="paypal" placeholder="paypal verification code"  value='paypal verification code'/></div>
				<div><textarea name="refer" id="refer" rows="6" placeholder="how did you hear about Survive Sac?">how did you hear about Survive Sac?</textarea></div>
				<div><input type="submit" id="submit" value="create player"/></div>
			</form>
		</div>
	<script type="text/javascript">
		$('input').click(function clearIfDefault(){
			$(this).val('');
		});
		$('textarea').click(function clearIfDefault(){
			$(this).val('');
		});
	</script>
	</body>
</html>""" % (urllib.urlencode({'team_name': team_name})))


class Team(webapp.RequestHandler):

	def post(self):

		team_name = self.request.get('team_name')
		player = Player(parent=team_key(team_name))
		player.full_name = self.request.get('full_name')
		player.age = self.request.get('age')
		player.email = self.request.get('email')
		player.refer = self.request.get('refer')
		
		previous_game = self.request.get('previous_game', False)

		if previous_game in set(['1', 'on', 'yes', 'checked', True, 1]):
			player.previous_game = True
		else:
			player.previous_game = False
		
		smartphone = self.request.get('smartphone', False)

		if smartphone in set(['1', 'on', 'yes', 'checked', True, 1]):
			player.smartphone = True
		else:
			player.smartphone = False

		paypal = self.request.get('paypal', False)
		if paypal != 'paypal verification code' and paypal not in set([False, None, 0]):
			player.paypal = self.request.get('paypal')
		else:
			self.redirect('/?' + urllib.urlencode({'fail': 'true', 'reason': 'paypal_invalid'}))

		logging.info('Subscribing player: '+str(player.full_name))
		k = player.put()
		
		if isinstance(k, db.Key):
			self.redirect('/?' + urllib.urlencode({'success': 'true'}))
		else:
			self.redirect('/?' + urllib.urlencode({'fail': 'true', 'reason': 'unknown'}))
		

TMD = webapp.WSGIApplication([
	('/', MainPage),
	('/create', Team)
	], debug=True)
	
	
def main():
	run_wsgi_app(TMD)

if __name__ == '__main__':
	main()