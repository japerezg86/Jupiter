#!/bin/bash
'
    ** Copyright (c) 2019, Autonomous Networks Research Group. All rights reserved.
    **     contributor: Quynh Nguyen and Bhaskar Krishnamachari
    **     Read license file in main directory for more details
'

service ssh start

echo 'Automatically run the CPU checking'

python3 -u cpu_test.py &
