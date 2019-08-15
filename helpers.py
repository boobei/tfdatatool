import csv
from selenium import webdriver
from selenium.webdriver.common.by import By
from seleniumrequests import Chrome
from selenium.webdriver.chrome.options import Options
import requests
import os
import re
import datetime as dt
from datetime import datetime

from flask import redirect, render_template, request, session
from functools import wraps

def createPath(path):
    if not os.path.exists(path):
        os.makedirs(path)

def apology(message, code=400):
    # render an error message
    return render_template("apology.html", top=code, bottom=message), code

def get_all_file_paths(directory):
    # initializing empty file paths list
    file_paths = []

    # crawling through directory and subdirectories
    for root, directories, files in os.walk(directory):
        for filename in files:
            # join the two strings in order to form the full filepath.
            filepath = os.path.join(root, filename)
            file_paths.append(filepath)

    # returning all file paths
    return file_paths

def tf_login(driver, tf_user, tf_pwd):
    driver.get("https://www.ticketfly.com/backstage")
    username = driver.find_element_by_id("email")
    username.clear()
    username.send_keys(tf_user)

    password = driver.find_element_by_name("password")
    password.clear()
    password.send_keys(tf_pwd)

    driver.find_element_by_name("_action_Submit").click()

def createPath(path):
    if not os.path.exists(path):
        os.makedirs(path)

def getGenres(driver, orgID):
    driver.get("https://www.ticketfly.com/backstage/genre/list/" + orgID)

    raw_table = driver.find_elements_by_css_selector("tbody")[0]
    table = raw_table.find_elements(By.TAG_NAME, "tr")

    regex = r"\/"
    cwd = os.getcwd()
    path = cwd + "/reports/" + orgID + "/genres"
    createPath(path)

    for row in table:
        r = row.find_elements(By.TAG_NAME, "td")
        name = re.sub(regex, "-", r[0].text)
        link = r[3].find_elements(By.LINK_TEXT, "Download")[0].get_attribute("href")

        # save file
        req = driver.request('GET', link)
        with open(path + "/" + name + ".csv", "wb") as new_file:
            new_file.write(req.content)

def getMemberGroups(driver, orgID):
    driver.get("https://www.ticketfly.com/backstage/memberGroup/list/" + orgID)

    raw_table = driver.find_elements_by_css_selector("tbody.ui-sortable")[0]
    table = raw_table.find_elements(By.TAG_NAME, "tr")

    regex = r"\/"
    cwd = os.getcwd()
    path = cwd + "/reports/" + orgID + "/member_groups"
    createPath(path)

    for row in table:
        r = row.find_elements(By.TAG_NAME, "td")
        name = re.sub(regex, "-", r[0].text)
        link = r[2].find_elements(By.LINK_TEXT, "Download")[0].get_attribute("href")

        # save file
        req = driver.request('GET', link)
        with open(path + "/" + name + ".csv", "wb") as new_file:
            new_file.write(req.content)

def getMembers(driver, orgID):
    link = "https://www.ticketfly.com/backstage/orgMember/exportMembers/" + orgID
    req = driver.request('GET', link)

    cwd = os.getcwd()
    path = cwd + "/reports/" + orgID
    createPath(path)

    with open(path + "/member_list.csv", "wb") as new_file:
        new_file.write(req.content)

def getSourcePerf(driver, orgID, start, end):
    driver.get("https://www.ticketfly.com/backstage/salesDashboard/channelPerformance/" + orgID)

    start_box = driver.find_element_by_name("reportStartDateString")
    start_box.clear()
    start_box.send_keys(start)

    end_box = driver.find_element_by_name("reportEndDateString")
    end_box.clear()
    end_box.send_keys(end)

    driver.find_element_by_name("_action_channelPerformance").click()

    link = "https://www.ticketfly.com/backstage/salesDashboard/channelPerformance/" + orgID + ".xls"
    req = driver.request('GET', link)

    cwd = os.getcwd()
    path = cwd + "/reports/" + orgID
    createPath(path)

    with open(path + "/source_performance.xls", "wb") as new_file:
        new_file.write(req.content)

def getPromoPerf(driver, orgID, start, end):
    start_object = datetime.strptime(start, "%m/%d/%Y")
    end_object = datetime.strptime(end, "%m/%d/%Y")
    end_object = end_object.replace(hour=23, minute=59, second=59)

    start_str = start_object.strftime("%m%%2F%d%%2F%Y+%I%%3A%M%%3A%S+%p&")
    end_str = end_object.strftime("%m%%2F%d%%2F%Y+%I%%3A%M%%3A%S+%p&")

    # magic string
    link = "https://www.ticketfly.com/backstage/orgReports/promotionReport/" + orgID + ".xls?fromString=" + start_str + "toString=" + end_str + "_action_promotionReport=Generate&format=xls"
    req = driver.request('GET', link)

    cwd = os.getcwd()
    path = cwd + "/reports/" + orgID
    createPath(path)

    with open(path + "/promo_performance.xls", "wb") as new_file:
        new_file.write(req.content)
