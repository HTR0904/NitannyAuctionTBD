from flask import Flask, render_template, request, redirect, url_for
import sqlite3 as sql

app = Flask(__name__)

#Allows html pages to be updated by refreshing without having to rerun the code
app.config['TEMPLATES_AUTO_RELOAD'] = True

host = 'http://127.0.0.1:5000/'


'''
TODO: 
- add DB connection
- add logic for handling different logins

'''


@app.route('/')
def index():
    # Renders the login page
    return render_template('login.html')

@app.route('/login_user', methods=['POST'])
def login_user():
    username = request.form.get('user_email')
    password = request.form.get('user_password')

    #check if credentials match, if not return an error like  "Invalid username or password."

    #Check user account type (bidder or seller) and determine which html page to redirect them to it:

    #Else, if account exists with these credential exists but no valid accounts type found (i.e. a helpdesk staff). Throw an error:
    return render_template('login.html')

@app.route('/login_helpdesk', methods=['POST'])
def login_user():
    helpdesk_username = request.form.get('helpdesk_email')
    helpdesk_password = request.form.get('helpdesk_password')

    #check if credentials match, if not return an error

    #Check user account type is a helpdesk account then redirect them to the html page.

    #Else, if account exists with these credential but is not a helpdesk staff (i.e. this is a regular user). Throw an error:
    return render_template('login.html')


if __name__ == '__main__':
    #app.run()
    app.run(debug=True)  #enabled to run with TEMPLATES_AUTO_RELOAD
