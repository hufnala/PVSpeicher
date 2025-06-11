#Imports
import requests
import json
import time
import configparser
import datetime 
import os
import sys
import csv

VersionStr="Version 09.06.25 12:15"

#read datapoint from generator
def get_generator_data(base_url, user, password, target):
    url = ''.join((base_url, target))
    #print(user, password, url)
    session = requests.Session()
    session.auth = (user, password)
    response = session.get(url)
    response.raise_for_status()
    #print(response.text)
    a = json.loads(response.text)
    value = float(a["value"])
    return value

#get dataset from generator
def load_generator_data():
    data=[
        datetime.datetime.now(),
        datetime.datetime.now().date(),
        get_generator_data(base, user, password, battery_load_url), 
        get_generator_data(base, user, password, act_prod_url),
        get_generator_data(base, user, password, act_consume_url),
        get_generator_data(base, user, password, act_charge_url)*-1,
        get_generator_data(base, user, password, act_grid_url),
        get_generator_data(base, user, password, cum_energy_prod),
        get_generator_data(base, user, password, cum_energy_cons),
        get_generator_data(base, user, password, cum_energy_charged),
        get_generator_data(base, user, password, cum_energy_discharged),
        get_generator_data(base, user, password, cum_grid_sell),
        get_generator_data(base, user, password, cum_grid_buy),
        get_generator_data(base, user, password, cum_DC_prod),
        get_generator_data(base, user, password, cum_AC_prod)		
        ]
    return data

#create datafiles if not existing
def create_pv_datafile(pv_file, ftype):
    with open(pv_file, 'w', newline='') as file:
            DataFile = csv.writer(file, delimiter =';')
            if ftype==1:
                DataFile.writerow(["TimeStamp","Date","BatteryLoad",
                           "Production","Consumption", "BatteryCharge","Grid","cum_produced", 
                           "cum_consumed", "cum_charged","cum_discharged", "cum_sell", "cum_buy"])
            elif ftype==2:
                DataFile.writerow(["TimeStamp","Date","Energy_FC","Energy_BS", "SunDWDraw","SunDWDhour"])			
	
#read data for prediction from websource
def FCS_fetch_predict_data(fn_url, fn_key, fn_lat_home, fn_lon_home, fn_dec_home, fn_az_home, fn_kwp_home):
    fn_kwp_home = float(fn_kwp_home)/1000
    url="https://api.forecast.solar/"+str(fn_key)+"/estimate/watthours/day/"+str(fn_lon_home)+"/"+ str(fn_lat_home)+"/"+str(fn_dec_home)+"/"+str(fn_az_home)+"/"+str(fn_kwp_home)
    #print(url)
    session = requests.Session()
    response = session.get(url)
    #print(response.text)
    predictData = json.loads(response.text)
    Data = predictData["result"]
    result = [datetime.datetime.now(), list(Data.keys())[0], list(Data.values())[0]]
    #print(result)
    return result

def BS_fetch_predict_data(myurl, mylat, mylon, myReqDate):
   ActTimeStamp=datetime.datetime.now()
   #ReqDate=datetime.date.today() + datetime.timedelta(days=1)
   #ReqDate=ReqDate.strftime('%Y-%m-%d')
   url = myurl+"lat="+lat_home+"&lon="+lon_home+"&date="+myReqDate
   session = requests.Session()
   #print ("GetData: " + url)
   response = session.get(url)
   predictData = json.loads(response.text)
   predictItems = len(predictData["weather"])
   i=0
   SolarCum=0
   readData=True
   while readData==True:
      #print(str(i))
      PredictTimeStamp = str(predictData['weather'][i]['timestamp'])
      ActSolar=predictData['weather'][i]['solar']
      SolarCum = SolarCum + ActSolar
      #print(PredictTimeStamp + " : " + str(SolarCum))
      if i < predictItems - 2:
           i=i+1
      else:
           readData=False
   act_pred_data = [ActTimeStamp, ReqDate, "BrightSky", round(SolarCum,3)]
   return act_pred_data

def getdwdsunhours(myurl, myReqDate ):
    session = requests.Session()
    response = session.get(myurl)
    predictData = json.loads(response.text)
    entries=len(predictData["days"])
    i=0
    readData=True
    while i<entries:
          PredictTimeStamp = str(predictData['days'][i]['dayDate'])
          PredictDuration = str(predictData['days'][i]['sunshine'])
          if PredictTimeStamp == myReqDate:
             act_pred_data = [PredictDuration, str(round(int(PredictDuration)/600,2))]
             break
          i=i+1
    result = act_pred_data
    return result

#write structured logfile 
def writelogfile(fn_file, fn_text, fn_value):
        logprint=False
        logdata=[datetime.datetime.now(), fn_text, fn_value]
        fn_file.writerow(logdata)
        if logprint:
            print(logdata)
			
#time format helper function
def get_time_format(data_in):
    result = datetime.datetime.strptime(str(data_in), '%H').time()

#renew discharge configuration
def update_dchg_configuration(file_name):
    config.read(file_name)
    globals()[dchg_start_hour]  = config['BatteryDischarge']['discharge_start_hour']
    globals()[dchg_stop_hour]   = config['BatteryDischarge']['discharge_stop_hour']
    globals()[max_dis_energy]   = config['BatteryDischarge']['max_discharge_energy']
   
    writelogfile(logwriter, "Discharge control", "configuration renewed")
	
#send discharge command to FEMS
def send_discharge_command(fn_user, fn_password, fn_base_url, fn_target, fn_dc_value):

    user = fn_user
    password = fn_password
    #url = 'http://192.168.1.40:80/rest/channel/ess0/SetActivePowerEquals'
    url = fn_base_url + fn_target
    #print(url)
    session = requests.Session()
    session.auth = (user, password)
    #print(session)
    data = {"value": fn_dc_value}
    #print(data)
    response = session.post(url, json = data)
    response = session.get(url)
    response.raise_for_status()
    #print(response.text)

#calculate discharge value
def calc_discharge_value(fn_battery_start, fn_battery_end, fn_battery_capacity, fn_duration):
    #print(fn_battery_start, fn_battery_end, fn_battery_capacity, fn_duration)
    dc_unload_capacity = (fn_battery_start-fn_battery_end)/100 * fn_battery_capacity #calculate W from percentage/capacity
    dc_unload = int(round(dc_unload_capacity/fn_duration,-2))
    return dc_unload	

def readdcsetup(cfg_file, month):
    import ast
    config = configparser.ConfigParser()
    cfg_file_name = cfg_file
    config.read(cfg_file_name)
    PredMin = ast.literal_eval(config['BatteryDischarge']['PredMin'])
    PredMinHours = ast.literal_eval(config['BatteryDischarge']['PredMinHours'])
    MinLoadLevel = ast.literal_eval(config['BatteryDischarge']['MinLoadLevel'])
    UnloadStop = ast.literal_eval(config['BatteryDischarge']['UnloadStop'])
    return PredMin[month-1], MinLoadLevel[month-1], UnloadStop[month-1], PredMinHours[month-1]

#read configuration from file
config = configparser.ConfigParser()
#cfg_file_name = r"/home/hufnala/Server/PVSystem.ini"
cfg_file_name = r"/home/alle/Fenecon/config/PVSystem.ini"
config.read(cfg_file_name)
DBPath           = config['Database']['FilePath']
DBFileProd       = config['Database']['FileNameProd']
DBFilePred       = config['Database']['FileNamePred']
log_path         = config['Logging']['FilePath']
log_file         = config['Logging']['FileName']
user             = config['PVGenerator']['User']
password         = config['PVGenerator']['Password']
base             = config['PVGenerator']['Base_url']
lon_home         = config['PVGenerator']['lon_home']
lat_home         = config['PVGenerator']['lat_home']
dec_home         = config['PVGenerator']['dec_home']
az_home          = config['PVGenerator']['az_home']
kwp_home         = config['PVGenerator']['kwp_home']
battery_capacity = config['PVGenerator']['battery_capactiy']
battery_load_url = config['PowerValues']['act_battery_load_url']
act_prod_url     = config['PowerValues']['act_product_url']
act_consume_url  = config['PowerValues']['act_consumption_url']
act_charge_url   = config['PowerValues']['act_charge_url']
act_grid_url     = config['PowerValues']['act_grid_url']
cum_energy_prod  = config['EnergyValues']['cum_energy_prod']
cum_energy_cons  = config['EnergyValues']['cum_energy_cons']
cum_energy_charged     = config['EnergyValues']['cum_energy_charge']
cum_energy_discharged  = config['EnergyValues']['cum_energy_discharge']
cum_grid_sell    = config['EnergyValues']['cum_energy_sell']
cum_grid_buy     = config['EnergyValues']['cum_energy_buy']
cum_DC_prod      = config['EnergyValues']['cum_DC_ProdEnergy']
cum_AC_prod      = config['EnergyValues']['cum_AC_ProdEnergy']
FCS_pred_url     = config['PredictDatabase']['FCS_BaseURL']
FCS_pred_key     = config['PredictDatabase']['FCS_Key']
BS_pred_url      = config['PredictDatabase']['BS_BaseURL']
DWD_pred_url     = config['PredictDatabase']['DWD_URL']

dchg_reconfigure = bool(config['BatteryDischarge']['reconfigure_active'])
dchg_man_ctrl_file=config['BatteryDischarge']['FileName']
dchg_start_hour  = config['BatteryDischarge']['discharge_start_hour'] 
dchg_stop_hour   = config['BatteryDischarge']['discharge_stop_hour'] 
#dchg_start_level = config['BatteryDischarge']['discharge_min_start_level']
#dchg_stop_level  = config['BatteryDischarge']['discharge_min_stop_level']
#pred_min_energy  = config['BatteryDischarge']['predict_min_energy']
max_dis_energy   = config['BatteryDischarge']['max_discharge_energy']
dc_url           = config['BatteryDischarge']['dc_url'] 


#main
print("PV System started - initialize logfile")
logfilename = os.path.join(log_path, log_file)

if os.path.exists(logfilename):
    print ("Open existing logfile")
    logfile = open(logfilename,'a')
    logwriter = csv.writer(logfile, delimiter =';')
else:
    print("Create New logfile")
    logfile = open(logfilename,'w')
    logwriter = csv.writer(logfile, delimiter =';')
        
writelogfile(logwriter, "System started", VersionStr )
pred_min_energy, dchg_start_level, dchg_stop_level, pred_min_hours=readdcsetup(cfg_file_name, datetime.datetime.now().month)
writelogfile(logwriter, "System", "fetched configuration: " + str(pred_min_energy) +":" + str(dchg_start_level)+":"+str(dchg_stop_level))

db_Produced = os.path.join(DBPath, DBFileProd)
print(db_Produced)
if os.path.exists(db_Produced):
    writelogfile(logwriter, "Production Database", "file exists")
else:
    writelogfile(logwriter, "Production Database", "create file")
    create_pv_datafile(db_Produced,1)
    
db_Predicted = os.path.join(DBPath, DBFilePred)
print(db_Predicted)
if os.path.exists(db_Predicted):
    writelogfile(logwriter, "Prediction Database", "file exists")
else:
    writelogfile(logwriter, "Prediction Database", "create file")
    create_pv_datafile(db_Predicted,2)  
 
writelogfile(logwriter, "System", "Initialize")

run_5min=True
run_1h  =True

discharge_active=False                                           #discharge off
run=1
predict_energy = 0                                               #initalize variable
start_discharge = False
stop_discharge = False
DC_ctrl=""
writelogfile(logwriter, "System", "initialized")

def deletectrlfile(Name):
    try:
        os.remove(dchg_man_ctrl_file)
        writelogfile(logwriter, "System","Manual control file deleted")
    except:
        writelogfile(logwriter, "System Error","Could not delete file")

#Manuelle Kontrolle löschen
#if os.path.exists(dchg_man_ctrl_file):
#      deletectrlfile(dchg_man_ctrl_file)

#SaveLogfile Startup
logfile.flush()
while run==1:                                                    #endless loop / service / every 30s
   
    if run_5min == True:   #ervy 5 min
            writelogfile(logwriter, "System","5min task started,  ")
            run_5min = False
            hour_now=str(int(datetime.datetime.now().strftime('%H'))).zfill(2)

            pv_dataset=load_generator_data()
            battery_load=pv_dataset[2]

            with open(db_Produced,'a') as prodfile:
                myProdwriter = csv.writer(prodfile, delimiter =';')
                myProdwriter.writerow(pv_dataset)
            writelogfile(logwriter, "Production Database", "updated")

            #check start time
            writelogfile(logwriter, "Logging Actual Hour", hour_now)
            writelogfile(logwriter, "Logging Start Hour",dchg_start_hour)

            if (run_1h == True):   #every hour
                    writelogfile(logwriter, "System","Hourly task started")
                    run_1h = False
                    try:
                        #Get prediction and update database
                        predict_update = FCS_fetch_predict_data(FCS_pred_url,FCS_pred_key,lon_home,lat_home,dec_home,az_home,kwp_home)
                        predict_data   = predict_update #keep old value on error
                        ReqDate=datetime.date.today().strftime('%Y-%m-%d')
                        predict_data1  = BS_fetch_predict_data(BS_pred_url, lat_home, lon_home,ReqDate)
                        predict_data2  = getdwdsunhours(DWD_pred_url, ReqDate)
                        predict_data.append(predict_data1[3])
                        predict_data.append(predict_data2[0])
                        predict_data.append(predict_data2[1])

                        #Save Prediction for control
                        predict_energy = predict_data[2]
                        predict_hours=predict_data2[1]

                        with open(db_Predicted,'a') as predfile:
                            myPredwriter = csv.writer(predfile, delimiter =';')
                            myPredwriter.writerow(predict_data)
                            writelogfile(logwriter, "Prediction Database","updated")
                    except:
                        writelogfile(logwriter, "Error - Update Prediction","failed")

                    #Reset System Settings daily
                    if (hour_now == "14"):
                        writelogfile(logwriter, "Daily reset","started")
                        try:
                            if os.path.exists(dchg_man_ctrl_file):
                                deletectrlfile(dchg_man_ctrl_file)
                        except:
                            writelogfile(logwriter, "Error Daily reset","delete config file failed")



                    #check discharge at starttime
                    if (hour_now == dchg_start_hour) and (discharge_active == False):       # Starttime & not active und only once
                        if (dchg_reconfigure==True):                         #read configuration
                            try:
                                writelogfile(logwriter, "Discharge control", "renew configuration")
                                update_dchg_configuration(cfg_file_name)
                                pred_min_energy, dchg_start_level, dchg_stop_level, pred_min_hours=readdcsetup(cfg_file_name, datetime.datetime.now().month)
                                time_start = get_time_format(dchg_start_hour)
                                time_stop  = get_time_format(dchg_stop_hour)
                            except:
                                writelogfile(logwriter, "Error - Discharge control", "renew configuration failed")
                        writelogfile(logwriter, "Discharge check", "Starthour reached "+ hour_now)

                        #check manual control
                        if os.path.exists(dchg_man_ctrl_file):
                            DC_ctrl = open(dchg_man_ctrl_file).readline()
                            #CheckStatus
                            if DC_ctrl=="Deaktiviert":
                                dchg_start_level="100"
                                writelogfile(logwriter, "Discharge control", "StartLevel changed to 100%")
                            elif DC_ctrl=="Limit50Prz":
                                dchg_stop_level='50'
                                writelogfile(logwriter, "Discharge control", "Limit changed to 50%")
                        else:
                                writelogfile(logwriter, "Discharge control", "No Control File Found")

                        #Preparation discharge to logfile
                        writelogfile(logwriter, "Battery load status [%]", str(battery_load))
                        writelogfile(logwriter, "Predicted Energy [Wh]", str(predict_energy))
                        writelogfile(logwriter, "Predicted Sunshine [h]", str(predict_hours))

                        #initialize discharge control
                        if (float(battery_load) >= float(dchg_start_level)):
                            writelogfile(logwriter, "Discharge control", "Battery load above level")
                            if ((float(predict_energy) > float(pred_min_energy)) or (float(predict_hours) > float(pred_min_hours))):
                                    start_discharge=True
                                    writelogfile(logwriter, "Discharge control", "Prediction above min expectation")
                            else:
                                    start_discharge=False
                                    writelogfile(logwriter, "Discharge control", "Prediction to low" )
                        else:
                            start_discharge=False
                            writelogfile(logwriter, "Discharge control", "Battery load to low")



                    if (start_discharge==True) and (discharge_active==False):
                        stop_discharge = False
                        writelogfile(logwriter, "Discharge control", "calculate values")
                        dc_unload_dur = float(dchg_stop_hour) - float(hour_now)
                        if (dc_unload_dur <= 0):
                            writelogfile(logwriter, "Discharge control", "negative duration - cancelled: " + str(dc_unload_dur))
                        else:
                            #writelogfile(logwriter, "Discharge control", "Values: " + str(battery_load) + str(dchg_stop_level)+str(battery_capacity) + str(dc_unload_dur))
                            dc_unload = calc_discharge_value(float(battery_load), float(dchg_stop_level), float(battery_capacity), dc_unload_dur )
                            writelogfile(logwriter, "Discharge control", "Calculated: " + str(dc_unload))
                            if dc_unload > int(max_dis_energy):
                                dc_unload=int(max_dis_energy)
                            discharge_active=True
                            writelogfile(logwriter, "Discharge control", "Started: " + str(dc_unload))
            logfile.flush()                 #save logfile latest after 5min
                    
    min_now=datetime.datetime.now()
    if min_now.minute % 5 == 0:
           run_5min = True

           if min_now.minute == 0:
              run_1h = True
           else:
              run_1h = False

    #if discharge active every 30s a comand to battery
    if (discharge_active == True):
        start_discharge = False
        send_discharge_command(user, password, base, dc_url, dc_unload)
        writelogfile(logwriter, "Discharge control", "Discharge Active: " + str(dc_unload)) 
        
        if (run_5min == True):
            try:
                battery_level = float(get_generator_data(base, user, password, battery_load_url))
            except:
                writelogfile(logwriter, "Discharge control", "Error battery level check - stop discharge")
                stop_discharge=True
                
            if battery_level <= float(dchg_stop_level): #off when limit is reached
                stop_discharge=True 
                writelogfile(logwriter, "Discharge control", "deactivated battery below limit: " + str(battery_level))
            else:
                writelogfile(logwriter, "Discharge control", "battery level: " + str(battery_level))
                
            hour_now=str(int(datetime.datetime.now().strftime('%H'))).zfill(2)
            if (hour_now == dchg_stop_hour):
                stop_discharge=True 
                writelogfile(logwriter, "Discharge control", "deactivated stop time reached") 
            else:
                writelogfile(logwriter, "Discharge control", "time not elapsed") 

    if (stop_discharge == True):
        discharge_active = False

    time.sleep(30)
logfile.close()
