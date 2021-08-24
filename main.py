import os
import pandas as pd
import requests
from flask import Flask, Markup, render_template, url_for, redirect, make_response, send_from_directory, request
from bs4 import BeautifulSoup

app = Flask(__name__, template_folder="templates")

# Enable debugging mode
app.config["DEBUG"] = True

# Load paths etc into app dict and initialise global variables
UPLOAD_FOLDER = 'static/files'
app.config['UPLOAD_FOLDER'] =  UPLOAD_FOLDER

fname = "MT PASA Changes - crosstab.csv"
app.config['DL_FNAME'] = fname

message = "Click to load Pasa data"
change_dict = dict()

# Root URL
@app.route('/', methods=['GET','POST'])
@app.route('/<int:lookback>', methods=['GET','POST'])
def index(lookback=1):
    # fetches the formed response from get nem pasa
    resp = get_nem_pasa(lookback)

    # button logic - updated variables dont seem to get into this!
    if request.method == 'POST':
        if request.form.get('action_dl')=='Download':
            return resp

    # render main page and pass dynamic data through        
    return render_template(
        'index.html',
        # status = status
        message = message,
        changeDict = change_dict
        )

# MTPASA with lookback
@app.route("/mtpasa/")
@app.route("/mtpasa/<int:lookback>")
def get_nem_pasa(lookback=1):

    global message
    global change_dict

    # Set URL inputs
    base_url = 'https://nemweb.com.au'
    nem_url = 'https://nemweb.com.au/Reports/Current/MTPASA_DUIDAvailability/'
    datelimit = '2025/12/31' #user adjustable
    lookback = int(lookback)+1

    # fetch and form list of files to download
    html_text = requests.get(nem_url).text
    soup = BeautifulSoup(html_text, 'html.parser')
    link_list = [link.get('href') for link in soup.find_all('a')][-lookback:]
    url1 = base_url + link_list[0]
    url2 = base_url + link_list[-1]

    # load files into DF
    df1 = pd.read_csv(url1)
    df1.rename(columns=df1.iloc[0],inplace=True) #set header row
    df1 = df1[df1.index != 'I']
    df1 = df1[df1.index != 'C']

    df2 = pd.read_csv(url2)
    df2.rename(columns=df2.iloc[0],inplace=True) #set header row
    df2 = df2[df2.index != 'I']
    df2 = df2[df2.index != 'C']

    # get dates for labelling
    first_date = df1.PUBLISH_DATETIME[0]
    second_date= df2.PUBLISH_DATETIME[0]

    # join the tables on day,region and DUID and convert to numeric
    df = pd.merge(df1[['DAY','REGIONID','DUID','PASAAVAILABILITY']],
                  df2[['DAY','REGIONID','DUID','PASAAVAILABILITY']],
                  how='left',
                  on=['DAY','REGIONID','DUID'], 
                  suffixes=[None,'_2']) 

    df.PASAAVAILABILITY = pd.to_numeric(df.PASAAVAILABILITY) # convert to numeric
    df.PASAAVAILABILITY_2 = pd.to_numeric(df.PASAAVAILABILITY_2) # convert to numeric

    # Create pasadelta as first datte minus second date
    # negative numbers are a decrease in availability
    # positive numbers are an increase in availability
    df['PASADELTA'] = df.PASAAVAILABILITY - df.PASAAVAILABILITY_2 # create pasadelta
    df['ABSPASADELTA'] = abs(df.PASADELTA)
    df = df[df.PASADELTA !=0] # drop rows with no change
    df = df[df.DAY<datelimit] # only take the next year, pivot the table to get columns for DUID, fillna()
  
    # If no changes return a shorter message and exit function
    if len(df.index) == 0:
        message = Markup(
        """No changes. <br>
        When comparing the MT PASA submitted on {} with {}, <br>
        """.format(first_date, second_date)
        )
        change_dict = ""
        return message
  
    # Set up df views and handle dynamic data, message and change_dict
    df_first = df.groupby('DUID').first()[['PASADELTA']] # look for the first entry for each
    plant_change_list = list(df.DUID.unique())
    message = Markup(
        """Availability has changed. <br>
        When comparing the MT PASA submitted on {} with {}, <br>
        There were {} plants that updated their availability.<br>
        The plants are listed below with the first change they made (Details in the attached files).
        """.format(first_date, second_date, len(plant_change_list))
        )

    change_dict = df_first[:10].to_dict()['PASADELTA'] # pass a dictionary of changes to the index page for sorting

    dfx = df[['DAY','DUID','PASADELTA']].pivot(index='DAY', columns='DUID',values='PASADELTA').fillna(0)

    # SERVE CSV AS DOWNLOAD
    resp = make_response(dfx.to_csv())
    resp.headers["Content-Disposition"] = "attachment; filename=PASADELTA.csv"
    resp.headers["Content-Type"] = "text/csv"
    return resp
    # return message

# Routing for download
# @app.route('/mtpasa/download', methods=['GET', 'POST'])
# def download():
#     # Appending app path to upload folder path within app root folder
#     uploads = (app.config['UPLOAD_FOLDER'])
#     # Returning file from appended path
#     return send_from_directory(directory=uploads, path=uploads, filename=fname)

if (__name__ == "__main__"):
    app.run(port = 5000)
