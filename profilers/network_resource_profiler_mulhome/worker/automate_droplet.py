
"""
.. note:: This is the main script to run in every node in the system for network profiling procedure.
"""

__author__ = "Quynh Nguyen, Pradipta Ghosh, Bhaskar Krishnamachari"
__copyright__ = "Copyright (c) 2019, Autonomous Networks Research Group. All rights reserved."
__license__ = "GPL"
__version__ = "2.1"

import random
import subprocess
import pyinotify
from apscheduler.schedulers.background import BackgroundScheduler
import os
import csv
import paramiko
from scp import SCPClient
from pymongo import MongoClient
import datetime
import pandas as pd
import numpy as np
import time
import sys
from os import listdir
from os.path import isfile, join
from os import path
import configparser
import requests
import time
import _thread
import psutil
import paho.mqtt.client as mqtt
from multiprocessing import Process, Manager
import logging





sys.path.append("../")

def retrieve_resource():
    mem = psutil.virtual_memory().percent
    cpu = psutil.cpu_percent()/ psutil.cpu_count()
    t = time.time()
    return mem,cpu,t

def schedule_monitor_resource(interval):
    """
    Schedulete the assignment update every interval
    
    Args:
        interval (int): chosen interval (minutes)
    
    """
    sched = BackgroundScheduler()
    sched.add_job(monitor_local_resources_EMA,'interval',id='assign_id', minutes=interval, replace_existing=True)
    sched.start()

def monitor_local_resources_EMA():
    """
    Obtain local resource stats (CPU, Memory usage and the lastest timestamp) from local node and store it to the variable ``local_resources``
    Using Exponential moving average
    """

    logging.debug('Updating local resource stats (EMA)')
    num_periods = 10 # EMA 10 periods
    cur_mem,cur_cpu,cur_time = retrieve_resource()
    if resource_profiling["count"] < (num_periods+1):
        resource_profiling["memory"] = (cur_mem + resource_profiling['memory'] * resource_profiling['count']) / (resource_profiling['count'] + 1)
        resource_profiling["cpu"] = (cur_cpu + resource_profiling['cpu'] * resource_profiling['count']) / (resource_profiling['count'] + 1)
    else:
        resource_profiling["memory"] = (cur_mem - resource_profiling["memory"])*(2/(num_periods+1)) + resource_profiling["memory"]
        resource_profiling["cpu"] = (cur_cpu - resource_profiling["cpu"])*(2/(num_periods+1)) + resource_profiling["cpu"]
    resource_profiling['count'] += 1
    resource_profiling['last_update'] = datetime.datetime.utcnow().strftime('%B %d %Y - %H:%M:%S')

    try:
        logdb  = resource_db[SELF_IP]
        new_log  = {'memory' : resource_profiling['memory'],
                    'cpu'    : resource_profiling['cpu'],
                    'count'  : resource_profiling['count'],
                    'last_update': resource_profiling['last_update']
                    }
        resource_id   = logdb.insert_one(new_log).inserted_id
    except Exception as e:
        logging.debug('Error logging resource profiling information')
        logging.debug(e)
        

def demo_help(server,port,topic,msg):
    try:
        logging.debug('Sending demo')
        username = 'anrgusc'
        password = 'anrgusc'
        client = mqtt.Client()
        client.username_pw_set(username,password)
        client.connect(server, port,300)
        client.publish(topic, msg,qos=1)
        client.disconnect()
    except Exception as e:
        logging.debug('Sending demo failed')
        logging.debug(e)
    

def does_file_exist_in_dir(path):
    """Check if file exist in directory
    
    Args:
        path (str): directory path
    
    Returns:
        bool: ``True`` if exist, ``False`` otherwise
    """

    return any(isfile(join(path, i)) for i in listdir(path))

def schedule_bokeh_profiling(interval):
    """
    Schedulete the assignment update every interval
    
    Args:
        interval (int): chosen interval (minutes)
    
    """
    sched = BackgroundScheduler()
    sched.add_job(announce_profiling,'interval',id='assign_id', seconds=interval, replace_existing=True)
    sched.start()

def announce_profiling():
    cur_mem,cur_cpu,cur_time = retrieve_resource()
    topic = 'poweroverhead_%s'%(SELF_NAME)
    msg = 'poweroverhead %s cpu %f memory %f timestamp %d \n' %(SELF_NAME,cur_cpu,cur_mem,cur_time)
    demo_help(BOKEH_SERVER,BOKEH_PORT,topic,msg)



class droplet_measurement():
    """
    This class deals with the network profiling measurements.
    """
    def __init__(self):
        self.username   = username
        self.password   = password
        self.file_size  = [1,10,100,1000,10000]
        self.dir_local  = dir_local
        self.dir_remote = dir_remote
        self.my_host    = None
        self.my_region  = None
        self.hosts      = []
        self.regions    = []
        self.scheduling_file    = dir_scheduler
        self.measurement_script = os.path.join(os.getcwd(),'droplet_scp_time_transfer')
        self.db = client_mongo.droplet_network_profiler
        self.logging = logging
        
    def do_add_host(self, file_hosts):
        """This function reads the ``scheduler.txt`` file to add other droplets info 
        
        Args:
            file_hosts (str): the path of ``scheduler.txt``
        """
        if file_hosts:
            with open(file_hosts, 'r') as f:
                reader = csv.reader(f, delimiter=',')
                header = next(reader, None)
                self.my_host   = header[0]
                self.my_region = header[1]
                for row in reader:
                    self.hosts.append(row[0])
                    self.regions.append(row[1])
        else:
            self.logging.debug("No detected droplets information... ")

    def do_log_measurement(self):
        """This function pick a random file size, send the file to all of the neighbors and log the transfer time in the local Mongo database.
        """
        for idx in range (0, len(self.hosts)):
            self.logging.debug('Probing random messages')
            random_size = random.choice(self.file_size)
            local_path  = '%s/%s_test_%dK'%(self.dir_local,self.my_host,random_size)
            remote_path = '%s'%(self.dir_remote)  
            # Run the measurement bash script     
            bash_script = self.measurement_script + " " +self.username + "@" + self.hosts[idx]
            bash_script = bash_script + " " + str(random_size)

            proc = subprocess.Popen(bash_script, shell = True, stdout = subprocess.PIPE)
            tmp = proc.stdout.read().strip().decode("utf-8")
            results = tmp.split(" ")[1]

            mins = float(results.split("m")[0])      # Get the minute part of the elapsed time
            secs = float(results.split("m")[1][:-1]) # Get the second potion of the elapsed time
            elapsed = mins * 60 + secs
            
            # Log the information in local mongodb
            cur_time = datetime.datetime.utcnow()
            logging  = self.db[self.hosts[idx]]
            new_log  = {"Source[IP]"        : self.my_host,
                        "Source[Reg]"       : self.my_region,
                        "Destination[IP]"   : self.hosts[idx],
                        "Destination[Reg]"  : self.regions[idx],
                        "Time_Stamp[UTC]"   : cur_time,
                        "File_Size[KB]"     : random_size,
                        "Transfer_Time[s]"  : elapsed}
            log_id   = logging.insert_one(new_log).inserted_id


class droplet_regression():
    """This class is used for the regression of the collected data
    """
    def __init__(self):
        self.db           = None
        self.my_host      = None
        self.my_region    = None
        self.hosts        = []
        self.regions      = []
        self.parameters_file = 'parameters_%s'%(sys.argv[1])
        self.dir_remote      = dir_remote_central
        self.scheduling_file = dir_scheduler
        self.db = client_mongo.droplet_network_profiler
        self.username = username
        self.password = password
        self.central_IPs = HOME_IP.split(':')
        self.central_IPs = self.central_IPs[1:]
        self.logging = logging
       
    def do_add_host(self, file_hosts):
        """This function reads the ``scheduler.txt`` file to add other droplets info 
        
        Args:
            file_hosts (str): the path of ``scheduler.txt``
        """
        if file_hosts:
            with open(file_hosts, 'r') as f:
                reader = csv.reader(f, delimiter=',')
                header = next(reader, None)
                self.my_host   = header[0]
                self.my_region = header[1]
                for row in reader:
                    self.hosts.append(row[0])
                    self.regions.append(row[1])
        else:
            self.logging.debug("No detected droplets information... ")

    def do_regression(self):
        """This function performs the regression on the collected data, store the quaratic parameters in the local database, and write parameters into text file.
        """
        self.logging.debug('Store regression parameters in MongoDB')
        regression = self.db[self.my_host]
        reg_cols   = ['Source[IP]',
                      'Source[Reg]',
                      'Destination[IP]',
                      'Destination[Reg]',
                      'Time_Stamp[UTC]',
                      'Parameters']
        reg_data   = []
        reg_data.append(reg_cols)

        for idx in range(0,len(self.hosts)):
            host    = self.hosts[idx]
            logging = self.db[host]
            cursor  = logging.find({})
            df      = pd.DataFrame(list(cursor))

            df['X'] = df['File_Size[KB]'] * 8 #Kbits
            df['Y'] = df['Transfer_Time[s]'] * 1000 #ms

            # Quadratic prediction
            quadratic  = np.polyfit(df['X'],df['Y'],2)
            parameters = " ".join(str(x) for x in quadratic)
            cur_time   = datetime.datetime.utcnow()
            
            new_reg = { "Source[IP]"       : self.my_host,
                        "Source[Reg]"      : self.my_region,
                        "Destination[IP]"  : self.hosts[idx],
                        "Destination[Reg]" : self.regions[idx],
                        "Time_Stamp[UTC]"  : cur_time,
                        "Parameters"       : parameters}
            reg_id    = regression.insert_one(new_reg).inserted_id
            reg_entry = [ self.my_host,
                          self.my_region,
                          self.hosts[idx],
                          self.regions[idx],
                          str(cur_time),
                          parameters ]

            reg_data.append(reg_entry)

        # Write parameters into text file
        with open(self.parameters_file, "w") as f:
            self.logging.debug('Writing into file........')
            writer = csv.writer(f)
            writer.writerows(reg_data)

    def do_send_parameters(self):
        """This function sends the local regression data to the central profiler
        """
        self.logging.debug('Send to central nodes')
        self.logging.debug(self.central_IPs)
        for central_IP in self.central_IPs:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(central_IP, username = self.username,
                                password = self.password, port = ssh_port)
            local_path  = os.path.join(os.getcwd(),self.parameters_file)
            remote_path = '%s'%(self.dir_remote)
            scp = SCPClient(client.get_transport())
            scp.put(local_path, remote_path)
            scp.close()


class MyEventHandler(pyinotify.ProcessEvent):
    """Setup the event handler for all the events
    """

    def __init__(self):
        self.Mjob = None
        self.Rjob = None
        self.cur_file = None
        self.logging = logging

    def prepare_database(self,filename):
        """Connect to MongoDB server, prepare the database ``droplet_network_profiler`` at every node
        
        Args:
            filename (str): info file having the node's name/IP address
        """

        client = MongoClient('mongodb://localhost:' + str(MONGO_DOCKER) + '/')
        db = client['droplet_network_profiler']
        c = 0
        with open(filename, 'r') as f:
            next(f)
            for line in f:
                c =c+1
                ip, region = line.split(',')
                db.create_collection(ip, capped=True, size=10000, max=10)
        with open(filename, 'r') as f:
            first_line = f.readline()
            ip, region = first_line.split(',')
            db.create_collection(ip, capped=True, size=100000, max=c*100)

    def regression_job(self):
        """Scheduling regression process every 10 minutes
        """
        self.logging.debug('Log regression every 10 minutes ....')
        d = droplet_regression()
        d.do_add_host(d.scheduling_file)
        d.do_regression()
        # d.do_send_parameters()

    def measurement_job(self):
        """Scheduling logging measurement process every minute
        """
        self.logging.debug('Log measurement every minute ....')
        d = droplet_measurement()
        d.do_add_host(d.scheduling_file)
        d.do_log_measurement()


    def process_IN_CLOSE_WRITE(self, event):
        """On every node, whenever there is scheduling information sent from the central network profiler:
            - Connect the database
            - Scheduling measurement procedure
            - Scheduling regression procedure
            - Start the schedulers
        
        Args:
            event (ProcessEvent): a new file is created
        """
        self.logging.debug("CREATE event: %s", event.pathname)
        if self.Mjob == None:
            self.logging.debug('Step 1: Prepare the database')
            self.prepare_database(event.pathname)
            sched = BackgroundScheduler()

            self.logging.debug('Step 2: Scheduling measurement job')
            sched.add_job(self.measurement_job,'interval',id='measurement', minutes=1, replace_existing=True)

            self.logging.debug('Step 3: Scheduling regression job')
            sched.add_job(self.regression_job,'interval', id='regression', minutes=10, replace_existing=True)

            self.logging.debug('Step 4: Start the schedulers')
            sched.start()

            while True:
                time.sleep(10)
            sched.shutdown()
        else:
             self.logging.debug('New scheduling file, setting up a new job')



def main():
    """Start watching process for ``scheduling`` folder.
    """

    global logging

    logging.basicConfig(level = logging.DEBUG)

    global username, password, ssh_port,num_retries, retry, dir_remote, dir_local, dir_scheduler, dir_remote_central, MONGO_DOCKER, MONGO_SVC, FLASK_SVC, FLASK_DOCKER, HOME_IP, SELF_IP

    # Load all the confuguration
    INI_PATH = '/network_profiling/jupiter_config.ini'

    config = configparser.ConfigParser()
    config.read(INI_PATH)

    username    = config['AUTH']['USERNAME']
    password    = config['AUTH']['PASSWORD']
    ssh_port    = int(config['PORT']['SSH_SVC'])
    num_retries = int(config['OTHER']['SSH_RETRY_NUM'])
    retry       = 1
    dir_local   = "generated_test"
    dir_remote  = "networkprofiling/received_test"
    dir_remote_central = "/network_profiling/parameters"
    dir_scheduler      = "scheduling/scheduling.txt"

    MONGO_SVC    = int(config['PORT']['MONGO_SVC'])
    MONGO_DOCKER = int(config['PORT']['MONGO_DOCKER'])
    FLASK_SVC    = int(config['PORT']['FLASK_SVC'])
    FLASK_DOCKER = int(config['PORT']['FLASK_DOCKER'])
    SELF_IP = os.environ["SELF_IP"]
    HOME_IP = os.environ["HOME_IP"]


    global BOKEH_SERVER, BOKEH_PORT, BOKEH, BOKEH_INTERVAL, SELF_NAME
    BOKEH_SERVER = config['BOKEH_LIST']['BOKEH_SERVER']
    BOKEH_PORT = int(config['BOKEH_LIST']['BOKEH_PORT'])
    BOKEH = int(config['BOKEH_LIST']['BOKEH'])
    BOKEH_INTERVAL = int(config['BOKEH_LIST']['BOKEH_INTERVAL'])
    SELF_NAME = os.environ['SELF_NAME']

    logging.debug('Bokeh information')
    logging.debug(BOKEH_SERVER)
    logging.debug(BOKEH_PORT)
    logging.debug(BOKEH)
    logging.debug(BOKEH_INTERVAL)
    logging.debug(SELF_NAME)

    global client_mongo 
    client_mongo = MongoClient('mongodb://localhost:' + str(MONGO_DOCKER) + '/')

    ## Resource profiling
    global manager,resource_profiling
    manager = Manager()
    resource_profiling = manager.dict()
    resource_profiling['count'] = 0
    resource_profiling['cpu'] = 0
    resource_profiling['memory'] = 0
    resource_profiling['last_update'] = None
    num_periods = 10
    interval = 1

    global resource_client, resource_db
    resource_client = MongoClient('mongodb://localhost:' + str(MONGO_DOCKER) + '/')
    resource_db = resource_client['central_resource_profiler']
    resource_db.create_collection(SELF_IP, capped=True, size = 100000, max=1000)


    if BOKEH==3:
        logging.debug('Start sending profiling information (CPU,mem) to the bokeh server')
        _thread.start_new_thread(schedule_bokeh_profiling,(BOKEH_INTERVAL,))

    # watch manager
    wm = pyinotify.WatchManager()
    wm.add_watch('scheduling', pyinotify.ALL_EVENTS, rec=True)
    logging.debug('starting the process\n')
    # event handler
    eh = MyEventHandler()
    # notifier
    notifier = pyinotify.Notifier(wm, eh)

    _thread.start_new_thread(schedule_monitor_resource,(interval,))

    notifier.loop()

if __name__ == '__main__':
    main()



