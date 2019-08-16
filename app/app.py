import os
import re
import yaml
import shutil
import datetime
from zipfile import ZipFile

# web stuff
import requests
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import exc, desc
from flask import Flask, flash, redirect, render_template, request, session, url_for, send_file
from flask_session import Session
from tempfile import mkdtemp

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from seleniumrequests import Chrome
from celery import Celery

from helpers import apology, tf_login, getMemberGroups, getMembers, getGenres, getSourcePerf, getPromoPerf, get_all_file_paths, org_exists
from flask_celery import make_celery

app = Flask(__name__)
# Configure session to use filesystem (instead of signed cookies)
project_dir = os.path.dirname(os.path.abspath(__file__))
database_file = "sqlite:///{}".format(os.path.join(project_dir, "ebtool.db"))
chromedriver_file = os.path.join(project_dir, "chromedriver")
app.config["CELERY_BROKER_URL"] = "redis://localhost:6379/0"
app.config["CELERY_RESULT_BACKEND"] = "redis://localhost:6379/0"
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
app.config["SQLALCHEMY_DATABASE_URI"] = database_file
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["CHROMEDRIVER_URI"] = chromedriver_file

celery = make_celery(app)

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Configure library to use SQLite database
db = SQLAlchemy(app)

Session(app)

class Request(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    time = db.Column(db.String)
    orgID = db.Column(db.String)
    username = db.Column(db.String)
    status = db.Column(db.String)
    filename = db.Column(db.String)
    def __repr__(self):
        return "id: {}, orgID: {}, username: {}, status: {}".format(self.id, self.orgID, self.username, self.status)

@app.route("/")
def index():
    return render_template("main.html")

@app.route("/queue")
def queue():
    queries = Request.query.order_by(desc(Request.id)).all()
    return render_template("queue.html", queries=queries)

@app.route("/download", methods=["POST"])
def download():
    filename = request.form.get("filename")
    return send_file(os.path.join("reports/", filename), as_attachment=True)

@app.route("/query", methods=["POST"])
def query():
    tf_user = request.form.get("tf_user")
    tf_pwd = request.form.get("tf_pwd")
    orgID = request.form.get("orgID")

    options = {}
    options["memberListCheck"] = request.form.get("memberListCheck")
    options["memberGroupsCheck"] = request.form.get("memberGroupsCheck")
    options["genreListCheck"] = request.form.get("genreListCheck")
    options["sourceCheck"] = request.form.get("sourceCheck")
    options["promoCheck"] = request.form.get("promoCheck")

    options["sourceStart"] = request.form.get("sourceStart")
    options["sourceEnd"] = request.form.get("sourceEnd")
    options["promoStart"] = request.form.get("promoStart")
    options["promoEnd"] = request.form.get("promoEnd")

    time = datetime.datetime.now().strftime("%m/%d/%Y, %H:%M:%S")
    new_request = Request(orgID=orgID, username=tf_user, status="Processing", time=time)

    # form validation - somple
    if not options["memberListCheck"] and not options["memberGroupsCheck"] and not options["genreListCheck"] and not options["sourceCheck"] and not options["promoCheck"]:
        return apology("Select at least one report")
    if options["sourceCheck"]:
        if not options["sourceStart"] or not options["sourceEnd"]:
            return apology("Date box unfilled")
    if options["promoCheck"]:
        if not options["promoStart"] or not options["promoEnd"]:
            return apology("Date box unfilled")

    # form validation - web stuff
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    driver = Chrome(chrome_options=chrome_options, executable_path=app.config["CHROMEDRIVER_URI"])
    login_result = tf_login(driver, tf_user, tf_pwd)
    if not login_result:
        return apology("Incorrect username / password")
    org_result = org_exists(driver, orgID)
    if not org_result:
        return apology("Invalid Organization ID")
    driver.quit()

    # process request
    db.session.add(new_request)
    db.session.commit()
    db.session.refresh(new_request)
    task = processing.delay(orgID, tf_user, tf_pwd, options, new_request.id)

    flash('Queued!')
    return render_template("main.html", tf_user=tf_user, tf_pwd=tf_pwd, memberListCheck = options["memberListCheck"], memberGroupsCheck = options["memberGroupsCheck"], genreListCheck=options["genreListCheck"], sourceCheck=options["sourceCheck"], promoCheck=options["promoCheck"], sourceStart=options["sourceStart"], sourceEnd=options["sourceEnd"], promoStart=options["promoStart"], promoEnd=options["promoEnd"])

@celery.task(name='tfly.collect')
def processing(orgID, tf_user, tf_pwd, options, request_id):
    # gets request object
    new_request = Request.query.filter_by(id=request_id).first()

    chrome_options = Options()
    chrome_options.add_argument("--headless")
    driver = Chrome(chrome_options=chrome_options, executable_path=app.config["CHROMEDRIVER_URI"])

    tf_login(driver, tf_user, tf_pwd)
    if options["memberListCheck"]:
        result = getMembers(driver, orgID)
        if not result:
            new_request.status = "Error with member groups"
            db.session.commit()
            driver.quit()
            return False
    if options["memberGroupsCheck"]:
        result = getMemberGroups(driver, orgID)
        if not result:
            new_request.status = "Error with member list"
            db.session.commit()
            driver.quit()
            return False
    if options["genreListCheck"]:
        result = getGenres(driver, orgID)
        if not result:
            new_request.status = "Error with genre report"
            db.session.commit()
            driver.quit()
            return False
    if options["sourceCheck"]:
        result = getSourcePerf(driver, orgID, options["sourceStart"], options["sourceEnd"])
        if not result:
            new_request.status = "Error with source report"
            db.session.commit()
            driver.quit()
            return False
    if options["promoCheck"]:
        result = getPromoPerf(driver, orgID, options["promoStart"], options["promoEnd"])
        if not result:
            new_request.status = "Error with promotion report"
            db.session.commit()
            driver.quit()
            return False

    driver.quit()

    # creates a zip then deletes the folder
    directory = "reports/" + orgID
    file_paths = get_all_file_paths(directory)

    # zips file
    filename = orgID + "_" + str(new_request.id) + ".zip"
    with ZipFile("reports/" + filename , 'w') as zip:
        for file in file_paths:
            zip.write(file)
    shutil.rmtree("reports/" + orgID)

    new_request.filename = filename
    new_request.status = "Done"
    db.session.commit()

def errorhandler(e):
    """Handle error"""
    return apology(e.name, e.code)

if __name__ == '__main__':
    app.run(host='0.0.0.0')
