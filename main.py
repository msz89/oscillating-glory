import os
import pandas as pd
import requests
from flask import Flask, Markup, render_template, url_for, redirect, make_response, send_from_directory, request
from bs4 import BeautifulSoup

app = Flask(__name__, template_folder="templates")

# enable debugging mode
app.config["DEBUG"] = True

# Upload folder
UPLOAD_FOLDER = 'static/files'
app.config['UPLOAD_FOLDER'] =  UPLOAD_FOLDER

fname = "MT PASA Changes - crosstab.csv"
app.config['DL_FNAME'] = fname
message = "Click to load Pasa data"
changeDict = dict()

# Root URL
@app.route('/', methods=['GET','POST'])
def index():

    getNEM() #could do 4 to do the full day lookback?
    if request.method == 'POST':
        if request.form.get('action_dl')=='Download':
            return redirect('/mtpasa/download')
     # Set The upload HTML template '\templates\index.html'
    return render_template(
      'index.html',
      # status = status
      message = message,
      changeDict = changeDict
      )


# mtpasa with lookback
@app.route("/mtpasa/")
@app.route("/mtpasa/<lookback>")
def getNEM(lookback=1):
  global message
  global changeDict

  base_url = 'https://nemweb.com.au'
  nem_url = 'https://nemweb.com.au/Reports/Current/MTPASA_DUIDAvailability/'
  datelimit = '2025/12/31' #user adjustable
  lookback = int(lookback)+1
              # url inputs

  html_text = requests.get(nem_url).text
  soup = BeautifulSoup(html_text, 'html.parser')
  link_list = [link.get('href') for link in soup.find_all('a')][-lookback:]
              # get the NEM web html, parse and make a list of the most recent 2 files

  url1 = base_url + link_list[0]
  url2 = base_url + link_list[-1]
              # form URLs for the files

  df1 = pd.read_csv(url1)
  df1.rename(columns=df1.iloc[0],inplace=True) #set header row
  df1 = df1[df1.index != 'I']
  df1 = df1[df1.index != 'C']
              # load older file into df

  df2 = pd.read_csv(url2)
  df2.rename(columns=df2.iloc[0],inplace=True) #set header row
  df2 = df2[df2.index != 'I']
  df2 = df2[df2.index != 'C']
              # load younger file into df

  firstdate = df1.PUBLISH_DATETIME[0]
  seconddate= df2.PUBLISH_DATETIME[0]
              # get dates for labelling

  df = pd.merge(df1[['DAY','REGIONID','DUID','PASAAVAILABILITY']],
                df2[['DAY','REGIONID','DUID','PASAAVAILABILITY']],
                how='left',
                on=['DAY','REGIONID','DUID'], 
                suffixes=[None,'_2']) # join the tables on day,region and DUID
  df.PASAAVAILABILITY = pd.to_numeric(df.PASAAVAILABILITY) # convert to numeric
  df.PASAAVAILABILITY_2 = pd.to_numeric(df.PASAAVAILABILITY_2) # convert to numeric
              # Join the tables together

  df['PASADELTA'] = df.PASAAVAILABILITY - df.PASAAVAILABILITY_2 # create pasadelta
  df['ABSPASADELTA'] = abs(df.PASADELTA)
  df = df[df.PASADELTA !=0] # drop rows with no change
  df = df[df.DAY<datelimit] # only take the next year, pivot the table to get columns for DUID, fillna()
                  # PASADELTA is first date - second date
  
  # Check for changes!
  if len(df.index) == 0:
      message = "No changes"
      return message
      # return redirect(url_for('.index'))
  
  ##!!! WEB APP BREAKS SOMEWHERE IN HERE! !!!

  # handle messaging
  df_first = df.groupby('DUID').first()[['PASADELTA']] # look for the first entry for each
  plantChangeList = list(df.DUID.unique())
  message = Markup(
      """There are changes. <br>
      When comparing the MT PASA submitted on {} with {}, <br>
      There were {} plants that updated their availability.<br>
      The plants are listed below with the first change they made (Details in the attached files).
      """.format(firstdate, seconddate, len(plantChangeList))
   )
  
  # pass a dictionary of changes to the index page for sorting
  changeDict = df_first[:5].to_dict()['PASADELTA']

  dfx = df[['DAY','DUID','PASADELTA']].pivot(index='DAY', columns='DUID',values='PASADELTA').fillna(0)
  savepath = os.path.join(app.config['UPLOAD_FOLDER'],fname)
  # how do I use flask for safe saving
  # dfx.to_csv(savepath)

  return message
  # return redirect(url_for('.index'))


@app.route('/mtpasa/download', methods=['GET', 'POST'])
def download():
    # Appending app path to upload folder path within app root folder
    uploads = (app.config['UPLOAD_FOLDER'])
    # Returning file from appended path
    return send_from_directory(directory=uploads, path=uploads, filename=fname)


if (__name__ == "__main__"):
     app.run(port = 5000)
