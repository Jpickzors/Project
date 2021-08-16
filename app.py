import os
from sqlite3.dbapi2 import Cursor

import requests
import validators
import sqlite3
import smtplib
from bs4 import BeautifulSoup
from lxml import etree as et
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from validators.url import url
from werkzeug.useragents import UserAgent
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import and_
import atexit
from helpers import check_email


def compare():

    d = db.session.query(Amazon).all()

    for entry in d:
        email = entry.email
        url = entry.url
        price = entry.priceAlert
        useragent = entry.useragent

        currentPrice = check_price(url, useragent)

        if currentPrice <= price:
            send_email(email, url, price)


app = Flask(__name__)

ENV = 'prod'

if ENV == 'dev':
    app.debug = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:123@localhost/amazon1'

else:
    app.debug = False
    app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://ofsuhgiilkyipq:42b6dce0475b68da87d1763404b71192236991faaea448af9f5c20a34a590044@ec2-54-83-82-187.compute-1.amazonaws.com:5432/dfu4u8shea2uc6'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class Amazon(db.Model):
    __tablename__ = 'amazon1'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String)
    url = db.Column(db.String)
    priceAlert = db.Column(db.Float)
    useragent = db.Column(db.String)

    def __init__(self, email, url, priceAlert, useragent):
        self.email = email
        self.url = url
        self.priceAlert = priceAlert
        self.useragent = useragent

if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
    scheduler = BackgroundScheduler()
    scheduler.add_job(func=compare, trigger="interval", hours=24)
    scheduler.start()

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)


@app.route("/", methods=["GET", "POST"])
def index():

    if request.method == "POST":

        link = request.form.get("url")

        if not validators.url(link):
            return render_template("index.html", message="Enter a valid URL (ex: https://...)")

        # user_agent = UserAgent(request.headers.get('User-Agent')).string

        # user_agent kept static to avoid Amazon blocking scraping access.
        user_agent = 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:80.0) Gecko/20100101 Firefox/80.0'

        headers = {"User-Agent": user_agent, "Referer": link}        

        page = requests.get(link, headers=headers)

        soup = BeautifulSoup(page.content, 'html.parser')

        title = soup.find(id="productTitle").get_text().strip()

        price = soup.find(id="priceblock_ourprice")

        if price == None:
           price = soup.find(id="priceblock_saleprice")
           if price == None:
                price = soup.find(id="priceblock_dealprice")

        price = price.get_text().strip()


        convertedPrice = (price[1:])

        convertedPrice = float(convertedPrice)
    
        return render_template("quoted.html", price=price, title=title, convertedPrice=convertedPrice, link=link)


    return render_template("index.html")


@app.route("/email", methods=["GET", "POST"])
def email():
    if request.method == "POST":

        #useragent = UserAgent(request.headers.get('User-Agent')).string

        useragent = 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:80.0) Gecko/20100101 Firefox/80.0'

        email = request.form.get("email")

        url = request.form.get("link")

        if bool(Amazon.query.filter_by(email=email, url=url).first()) == True:
            return render_template("index.html", error1='You have already inserted this email and URL into the database! Try again with a different product!')

        if url == '' or email == '':
            return "Please enter the required fields"

        priceAlert = float(request.form.get("priceAlert"))

        if priceAlert <= 0:
            return "Enter a positive number"

        if not check_email(email):
            return "Invalid Email"
        
        data = (Amazon(email, url, priceAlert, useragent))
        db.session.add(data)
        db.session.commit()

        return render_template("index.html", message1="Success! An email will be sent once the price is at or below your target price! We will send an email every 24 hrs to remind you. To remove your entry from the Price Tracker, please visit the 'Remove Alert' tab!")

    return redirect("/")

@app.route("/remove", methods=["GET", "POST"])
def remove():

    if request.method == "POST":
        
        url_1 = request.form.get("url")
        email_1 = request.form.get("email")

        if url == '' or email == '':
            return render_template('remove.html', message='Please enter the required fields')

        if bool(Amazon.query.filter_by(email=email_1, url=url_1).first()) == True:
            Amazon.query.filter_by(email=email_1, url=url_1).delete()
            db.session.commit()

            return render_template("index.html", message2='The Price Alert has been removed!')

        else:
            return render_template("remove.html", error='Data not found in Database. Are you sure you had entered the information correctly?')             

    return render_template("remove.html")


def check_price(url, useragent):

    headers = {"User-Agent": useragent, "Referer": url}

    page = requests.get(url, headers=headers)

    soup = BeautifulSoup(page.content, 'html.parser')
    
    price = soup.find(id="priceblock_ourprice")

    if price == None:
        price = soup.find(id="priceblock_saleprice")
        if price == None:
            price = soup.find(id="priceblock_dealprice")

    price = price.get_text().strip()

    convertedPrice = (price[1:])

    convertedPrice = float(convertedPrice)

    return convertedPrice


def send_email(email, link, price):

    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.ehlo()
    server.starttls()
    server.ehlo()

    server.login('ama.zon.price.tracker2@gmail.com', 'oscnyfjzyflsdlzb')

    remove_link = 'https://ama-zon-price-tracker.herokuapp.com/remove'

    subject = 'Amazon Price Tracker: The Price Fell Below Your Target!'
    body = f'Your tracked item fell below your target price of {price}. \r\r\nCheck the Amazon link: {link}.  \r\r\nTo cancel alerts, visit {remove_link}.'

    msg = f'Subject: {subject}\n\n{body}'

    server.sendmail('justin.picks88@gmail.com', f'{email}', msg)

    print('Email has been sent!')

    server.quit()

if __name__ == '__main__':

    app.run()