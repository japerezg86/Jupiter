#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
    .. note:: This script is used entirely for evaluation purpose.
"""

__author__ = "Quynh Nguyen, Pradipta Ghosh, and Bhaskar Krishnamachari"
__copyright__ = "Copyright (c) 2019, Autonomous Networks Research Group. All rights reserved."
__license__ = "GPL"
__version__ = "2.1"


import shutil
import os
import random
import time
import logging



def evaluate_random():
    """
    Copy files from folder ``sample_input`` to folder ``input`` at random intervals for evaluation 
    
    """
    file_count = len(os.listdir("sample_input/")) 
    interval = 120
    for i in range(1,file_count+1):
        n = random.randint(1,interval)
        count = 0
        while count<n:
            count = count+1
            time.sleep(1)
        src = "sample_input/%dbotnet.ipsum"%i
        dest = "input/%dbotnet.ipsum"%i
        logging.debug('---- Generate random input files')
        shutil.copyfile(src,dest)

def evaluate_interval(interval):
    """
    Copy files from folder ``sample_input`` to folder ``input`` at regular intervals for evaluation 

    Args:
        interval (int): interval time to inject the sample input file
    
    """
    file_count = len(os.listdir("sample_input/")) 
    for i in range(1,file_count+1):
        count = 0
        while count<interval:
            count = count+1
            time.sleep(1)
        src = "sample_input/%dbotnet.ipsum"%i
        dest = "input/%dbotnet.ipsum"%i
        logging.debug('---- Generate random input files')
        shutil.copyfile(src,dest)

def evaluate_sequential():
    """
    Copy files from folder ``sample_input`` to folder ``input`` one after another for evaluation 
    
    """

    file_count = len(os.listdir("sample_input/"))
    file_count_out = len(os.listdir("output/"))
    logging.debug('---- Generate random input files')
    for i in range(1,file_count+1):
        src = "sample_input/%dbotnet.ipsum"%i
        dest = "input/%dbotnet.ipsum"%i
        logging.debug('---- Generate random input files')
        shutil.copyfile(src,dest)
        count = 0
        while 1:
            time.sleep(5)
            file_count_out = len(os.listdir("output/"))
            if file_count_out ==  i:
                break


    logging.debug('---- Finish generating sequential input files')
    

if __name__ == '__main__':
    #evaluate_random()
    global logging
    logging.basicConfig(level = logging.DEBUG)

    my_id = os.environ['TASK']
    logging.debug(my_id)
    n = my_id.split('home')
    
    num = 1
    if n[1].isdigit():
        num = float(n[1])
    sleep_time_default = 240
    sleep_time = sleep_time_default + (num-1)*120
    logging.debug('The delay to send sample files')
    time.sleep(sleep_time)
    logging.debug('Start copying sample files for evaluation')
    evaluate_sequential()