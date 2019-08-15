import os

# web stuff
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import exc, desc
from flask import Flask, flash, redirect, render_template, request, session, url_for, send_file
from flask_session import Session
from tempfile import mkdtemp

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from seleniumrequests import Chrome

from zipfile import ZipFile
import datetime
import requests
import shutil
import re

from helpers import apology, tf_login, getMemberGroups, getMembers, getGenres, getSourcePerf, getPromoPerf, get_all_file_paths, processing

# Configure application
app = Flask(__name__)

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Configure library to use SQLite database
project_dir = os.path.dirname(os.path.abspath(__file__))
database_file = "sqlite:///{}".format(os.path.join(project_dir, "ebtool.db"))
db = SQLAlchemy(app)

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
app.config["SQLALCHEMY_DATABASE_URI"] = database_file
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
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

    # print(orgID, memberListCheck, memberGroupsCheck, genreListCheck, sourceCheck, promoCheck, sourceStart, sourceEnd, promoStart, promoEnd)

    cur_dir = os.getcwd()
    chromedriver_location = cur_dir + "/chromedriver"

    time = datetime.datetime.now().strftime("%m/%d/%Y, %H:%M:%S")
    new_request = Request(orgID=orgID, username=tf_user, status="Processing", time=time)
    db.session.add(new_request)
    db.session.commit()

    # process request
    processing(driver, tf_user, tf_pwd, options, chromedriver_location)

    # creates a zip then deletes the folder
    directory = "reports/" + orgID
    file_paths = get_all_file_paths(directory)
    db.session.refresh(new_request)
    filename = orgID + "_" + str(new_request.id) + ".zip"
    with ZipFile("reports/" + filename , 'w') as zip:
        for file in file_paths:
            zip.write(file)
    shutil.rmtree("reports/" + orgID)

    new_request.filename = filename
    new_request.status = "Done"
    db.session.commit()

    flash('Done!')
    return render_template("main.html", tf_user=tf_user, tf_pwd=tf_pwd)


def errorhandler(e):
    """Handle error"""
    return apology(e.name, e.code)
