from flask import Flask
from flask import jsonify
from flask import request
from datetime import datetime
import json
import configparser
import collections
import os
import sys
import queue
import threading
import logging
import time
import string
import random
import _thread
import shutil




try:
    # successful if running in container
    sys.path.append("/jupiter/build")
    from jupiter_utils import app_config_parser
except ModuleNotFoundError:
    # Python file must be running locally for testing
    sys.path.append("../../core/")
    from jupiter_utils import app_config_parser

import ccdag

APP_DIR = os.path.dirname(os.path.abspath(__file__))

# Parse app_config.yaml. Keep as a global to use in your app code.
app_config = app_config_parser.AppConfig(APP_DIR)


# Parse app_config.yaml. Keep as a global to use in your app code.
config = configparser.ConfigParser()
config.read(ccdag.JUPITER_CONFIG_INI_PATH)

FLASK_DOCKER = int(config['PORT']['FLASK_DOCKER'])
FLASK_SVC   = int(config['PORT']['FLASK_SVC'])

global collagejobs, log
log = []

app = Flask('Global_Server')

logging.basicConfig(format="%(levelname)s:%(filename)s:%(message)s")
logg = logging.getLogger(__name__)
logg.setLevel(logging.DEBUG)






class collageJobs(object):
    def __init__(self):
        self.current_job_id = 0
        self.num_tasks = 9
        self.job_files_dict = collections.defaultdict(list)
        self.job_resnet_preds_dict = collections.defaultdict(list)
        self.job_collage_preds_dict = collections.defaultdict(list)
        self.processed_jobids = []
    def get_id(self):
        self.job_resnet_preds_dict[self.current_job_id] = [-1] * self.num_tasks
        return self.current_job_id
    def put_files(self, job_id, filelist): 
        self.job_files_dict[job_id] = filelist
        self.current_job_id += 1
        return self.current_job_id
    def put_resnet_pred(self, job_id, pred, task_num):
        #print("job_id, resnet task_num, resnet preds for this job id", job_id, task_num, self.job_resnet_preds_dict[job_id])
        print("already processed job_ids", self.processed_jobids)
        if job_id in self.processed_jobids:
            return -1
        else:
            self.job_resnet_preds_dict[job_id][task_num] = pred
            return job_id
    def put_collage_preds(self, job_id, preds):
        print('Adding job collage prediction')
        self.job_collage_preds_dict[job_id] = preds
        print(self.job_collage_preds_dict)
    def enough_resnet_preds(self, job_id):
        if self.job_resnet_preds_dict[job_id].count(-1) >= ccdag.RESNETS_THRESHOLD: # not enough resnet task predictions. too early for this jobid.
            print("current count {}, resnets_threshold {}".format(self.job_resnet_preds_dict[job_id].count(-1), ccdag.RESNETS_THRESHOLD))
            return False
        else:
            return True
    
    def get_missing_dict(self):
    # There is collage prediction and some missing resnet predictions
        missing_files_preds_dict = {}
        job_ids = list(self.job_files_dict.keys())
        print("already processed job_ids")
        print(self.processed_jobids)
        #print("all job ids")
        #print(job_ids)
        for job_id in job_ids:
            if job_id in self.processed_jobids: # already processed
                continue
            missing = []
            if self.job_resnet_preds_dict[job_id].count(-1) >= ccdag.RESNETS_THRESHOLD: # not enough resnet task predictions. too early for this jobid.
                continue
                #for i in range(self.num_tasks):
                #    missing.append(i)
            else:
                for idx, p in enumerate(self.job_resnet_preds_dict[job_id]):# Find missing resnet predictions
                    if p == -1:
                        missing.append(idx)
            print("missing tasks nums for jobid %s are %s" %(job_id, missing))
            if len(missing) > 0:
                print("Job collage prediction")
                print(self.job_collage_preds_dict)
                if job_id in self.job_collage_preds_dict:# if collage predictions found
                    for idx in missing:
                        #logging.debug(task)
                        missing_pred = self.job_collage_preds_dict[job_id][idx]
                        if missing_pred != -1:
                            missing_file = self.job_files_dict[job_id][idx]
                            missing_files_preds_dict[missing_file] = missing_pred
                    self.processed_jobids.append(job_id)
            else: # len(missing) == 0. all resnet predictions are available.
                self.processed_jobids.append(job_id)
                
        return missing_files_preds_dict

class EventLog(object):
        def __init__(self):
            self.id = 1
            self.job_dict = {'1':[]}
        def get_id(self):
            return self.id
        def id_update(self):
            self.id+=1
            self.job_dict[str(self.id)] = [] # when the new job comes, we add a list to the dictionary for this new job
        def get_dict(self):
            return self.job_dict
        def dict_update(self,job_id,filename):
            self.job_dict[job_id].append(filename) # update the received result to dictionary



### Krishna
@app.route('/post-prediction-resnet', methods=['POST'])
def request_resnet_prediction():
    recv = request.get_json()
    job_id = recv['job_id']
    prediction = recv['msg']
    resnet_task_num = recv['resnet_task_num']
    print('Receive the prediction from resnet for job id', job_id, resnet_task_num)
    ret_val = collagejobs.put_resnet_pred(job_id, prediction, resnet_task_num)
    response = ret_val
    print(collagejobs.job_resnet_preds_dict)
    return json.dumps(response)

@app.route('/post-enough-resnet-preds', methods=['POST'])
def request_enough_resnet_preds():
    recv = request.get_json()
    job_id = recv['job_id']
    print('received enough resnet preds for jobid', job_id)
    ret_val = collagejobs.enough_resnet_preds(job_id)
    response = ret_val
    return json.dumps(response)

@app.route('/post-predictions-collage', methods=['POST'])
def request_collage_prediction():
    recv = request.get_json()
    job_id = recv['job_id']
    print('Receive the prediction from collage for job id', job_id)
    final_preds = recv['msg']
    print(final_preds)
    collagejobs.put_collage_preds(job_id, final_preds)
    response = job_id
    #print("posted predictions from collage: ", job_id, final_preds)
    #print("collage preds dict: ", collagejobs.job_collage_preds_dict)
    return json.dumps(response)

@app.route('/post-id-master', methods=['POST'])
def request_id_master():
    recv = request.get_json()
    response = collagejobs.get_id()
    print("New job id is: ", response)
    return json.dumps(response)

@app.route('/post-files-master', methods=['POST'])
def request_post_files():
    recv = request.get_json()
    job_id = recv['job_id']
    filelist = recv['filelist']
    #print("File list for job id %s is %s " % (job_id, filelist))
    response = collagejobs.put_files(job_id, filelist)
    print(collagejobs.job_files_dict)
    return json.dumps(response)

@app.route('/post-get-images-master', methods=['POST'])
def request_post_get_images():
    recv = request.get_json()
    #print("post-get-images: before processing")
    #print(collagejobs.job_files_dict)
    #print(collagejobs.job_resnet_preds_dict)
    #print(collagejobs.job_collage_preds_dict)
    response = collagejobs.get_missing_dict()
    print("missing files dict: ")
    print(response)
    #print("post-get-images: after processing")
    #print(collagejobs.job_files_dict)
    #print(collagejobs.job_resnet_preds_dict)
    #print(collagejobs.job_collage_preds_dict)
    return json.dumps(response)
    

### Krishna

# function of job_id response
@app.route('/post-id', methods=['POST'])
def request_id():
    print('Receive LCC job id request')
    recv = request.get_json()
    class_image = recv['class_image']
    print('********************')
    print(class_image)
    print(log[class_image-1])
    response = str(log[class_image-1].get_id())
    log[class_image-1].id_update()
    print(response)
    return json.dumps(response)
    
# function of dictionary response
@app.route('/post-dict',methods=['POST'])
def request_dict():
    print('Receive LCC job dictionary request')
    recv = request.get_json()
    class_image = recv['class_image']
    print('********************')
    print(class_image)
    print(log[class_image-1])
    log[class_image-1].dict_update(recv['job_id'],recv['filename'])
    response = log[class_image-1].get_dict()
    print(response)
    return json.dumps(response)

collagejobs = collageJobs()
for i in range(ccdag.NUM_CLASS):
    event = EventLog()
    log.append(event)
app.run(threaded = True, host = '0.0.0.0',port = FLASK_DOCKER) #address

def task(q, pathin, pathout, task_name):
    logg.info(f"Starting non-DAG task {task_name}")
    children = app_config.child_tasks(task_name)
    while True:
        time.sleep(1)
    


   

    
