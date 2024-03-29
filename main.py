import datetime
from bs4.builder import TreeBuilder
import pandas as pd
import requests
from flask import Flask, Markup, make_response, render_template, request
from bs4 import BeautifulSoup

app = Flask(__name__, template_folder="templates")

# Enable debugging mode
app.config["DEBUG"] = True
# Load paths etc into app dict and initialise global variables
UPLOAD_FOLDER = 'static/files'
app.config['UPLOAD_FOLDER'] =  UPLOAD_FOLDER
app.config['CHANGECOUNT'] = dict()
app.config['STATUSCOLOUR'] = "lightgrey"


# Root URL
@app.route('/', methods=['GET','POST'])
@app.route('/<int:lookback>', methods=['GET','POST'])
def index(lookback=1):
    # fetches the formed response from get nem pasa
    # period = request.args.get('period') # better way to use params rather than endpoint

    flag,message,changes,resp = get_nem_pasa(lookback)

    # button logic - updated variables dont seem to get into this!
    if request.method == 'POST':
        return resp

    # render main page and pass dynamic data through
    return render_template(
        'index.html',
        # status = status
        message = message,
        changeDict = changes,
        changeCount = app.config['CHANGECOUNT'],
        period = lookback,
        statuscolour = app.config['STATUSCOLOUR']
        )


# MTPASA with lookback
@app.route("/mtpasa/")
@app.route("/mtpasa/<int:lookback>")
def get_nem_pasa(lookback=1):

    # Set URL inputs
    base_url = 'https://nemweb.com.au'
    nem_url = 'https://nemweb.com.au/Reports/Current/MTPASA_DUIDAvailability/'
    date_today = datetime.date.today()
    datelimit = str(datetime.date(date_today.year+5,date_today.month,date_today.day))

    lookback = int(lookback)+1

    # fetch and form list of files to download
    html_text = requests.get(nem_url).text
    soup = BeautifulSoup(html_text, 'html.parser')
    link_list = [link.get('href') for link in soup.find_all('a')][-lookback:]
    url1 = base_url + link_list[0]
    url2 = base_url + link_list[-1]

    # load files into DF

#!!!!d type={'user_id': int} dont guess date-time like a chump!

    df1 = pd.read_csv(url1, index_col=False)
    df1.rename(columns=df1.iloc[0],inplace=True) #set header row
    df1.set_index(keys="I",inplace=True)
    df1 = df1[df1.index != 'I']
    df1 = df1[df1.index != 'C']

    df2 = pd.read_csv(url2, index_col=False)
    df2.rename(columns=df2.iloc[0],inplace=True) #set header row
    df2.set_index(keys="I",inplace=True)
    df2 = df2[df2.index != 'I']
    df2 = df2[df2.index != 'C']

    # get dates for labelling
    first_date = df1.PUBLISH_DATETIME[0]
    second_date = df2.PUBLISH_DATETIME[0]
    
 
    # join the tables on day,region and DUID and convert to numeric
    df = pd.merge(df1[['DAY','REGIONID','DUID','PASAAVAILABILITY']],
                  df2[['DAY','REGIONID','DUID','PASAAVAILABILITY']],
                  how='outer',
                  on=['DAY','REGIONID','DUID'], 
                  suffixes=[None,'_2'])
    df.fillna(value=0, inplace=True)
    df["PASAAVAILABILITY"] = pd.to_numeric(df["PASAAVAILABILITY"]) # convert to numeric
    df["PASAAVAILABILITY_2"] = pd.to_numeric(df["PASAAVAILABILITY_2"]) # convert to numeric

    # Create pasadelta as second date minus first date
    # negative numbers are a decrease in availability
    # positive numbers are an increase in availability
    df['PASADELTA'] = df.PASAAVAILABILITY_2 - df.PASAAVAILABILITY # create pasadelta
    df['ABSPASADELTA'] = abs(df.PASADELTA)

    df = df[df.PASADELTA !=0] # drop rows with no change
    df = df[df.DAY<datelimit] # only take the next year, pivot the table to get columns for DUID, fillna()

    #Import the STATION Names // DUID to match
    DUID = pd.read_csv("NEM_DUID_LOOKUP.csv") 
    df = df.merge(DUID,how='left')

    # If no changes return a shorter message and exit function
    if len(df.index) == 0:
        #build up the tuple of flag, message and changes (bool, str, dict)
        flag = False
        message = Markup(
        """No changes. <br>
        When comparing the MT PASA submitted on {} with {}, <br>
        """.format(first_date, second_date)
        )
        changes = ""
        resp=""
        app.config['STATUSCOLOUR']="lightgrey"
        return (flag, message, changes, resp)
  
    # Set up df views and handle dynamic data, message and changes
    df_first = df.groupby('DUID').first().sort_values('ABSPASADELTA',ascending=False)#[['PASADELTA']] # look for the first entry for each
    df_first['DAY'] = pd.to_datetime(df_first.DAY).dt.strftime('%d/%m/%Y')

    plant_change_list = list(df.DUID.unique())
    #build up the tuple of flag, message and changes (bool, str, dict)
    flag = True
    message = Markup(
        """Availability has changed. <br>
        When comparing the MT PASA submitted on {} with {}, <br>
        There were {} plants that updated their availability.<br>
        The plants are listed below with the first change they made (Details in the attached files).
        """.format(first_date, second_date, len(plant_change_list))
        )

    changes = df_first[:10].to_dict('index')#['PASADELTA'] # pass a dictionary of changes to the index page for sorting

    app.config['STATUSCOLOUR'] = "#05B59E"
    app.config['CHANGECOUNT'] = df.groupby('DUID').count()[['PASADELTA']].to_dict() #df_counts

    # SERVE CSV AS DOWNLOAD
    dfx = df[['DAY','DUID','PASADELTA']].pivot(index='DAY', columns='DUID',values='PASADELTA').fillna(0)
    resp = make_response(dfx.to_csv())
    resp.headers["Content-Disposition"] = "attachment; filename=PASADELTA.csv"
    resp.headers["Content-Type"] = "text/csv"
    return (flag, message, changes, resp)

if (__name__ == "__main__"):
    app.run(port = 5000)
