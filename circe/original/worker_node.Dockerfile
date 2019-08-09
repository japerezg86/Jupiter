# Instructions copied from - https://hub.docker.com/_/python/
FROM ubuntu:16.04

RUN apt-get -yqq update && apt-get install -y --no-install-recommends apt-utils
RUN apt-get -yqq install python3-pip python3-dev libssl-dev libffi-dev 
RUN apt-get install -yqq openssh-client openssh-server bzip2 wget net-tools sshpass screen
RUN apt-get install -y vim
RUN apt-get install g++ make openmpi-bin libopenmpi-dev -y
RUN apt-get install sudo -y
RUN apt-get install iproute2 -y

## Install TASK specific needs. The hadoop is a requirement for the network profiler application
##RUN wget http://supergsego.com/apache/hadoop/common/hadoop-2.8.1/hadoop-2.8.1.tar.gz -P ~/
RUN wget https://archive.apache.org/dist/hadoop/core/hadoop-2.8.1/hadoop-2.8.1.tar.gz -P ~/
RUN tar -zxvf ~/hadoop-2.8.1.tar.gz -C ~/
RUN rm ~/hadoop-2.8.1.tar.gz
RUN sudo apt update
RUN apt-get install -y mosquitto-clients

ADD circe/original/requirements.txt /requirements.txt

RUN pip3 install -r requirements.txt
RUN echo 'root:PASSWORD' | chpasswd
RUN sed -i 's/PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config
RUN sed -i 's/PermitRootLogin without-password/PermitRootLogin yes/' /etc/ssh/sshd_config
RUN sed -i 's/#PermitRootLogin yes/PermitRootLogin yes/' /etc/ssh/sshd_config

# SSH login fix. Otherwise user is kicked off after login
RUN sed 's@session\s*required\s*pam_loginuid.so@session optional pam_loginuid.so@g' -i /etc/pam.d/sshd

ENV NOTVISIBLE "in users profile"
RUN echo "export VISIBLE=now" >> /etc/profile

RUN mkdir -p /centralized_scheduler/input
RUN mkdir -p /centralized_scheduler/output
#RUN mkdir -p /centralized_scheduler/runtime
ADD circe/original/monitor.py /centralized_scheduler/monitor.py
ADD circe/original/stress_test.py /stress_test.py
ADD circe/original/cpu_test.py /cpu_test.py
RUN mkdir -p /home/darpa/apps/data

#ADD circe/original/rt_profiler_data_update.py  /centralized_scheduler/rt_profiler_data_update.py

# IF YOU WANNA DEPLOY A DIFFERENT APPLICATION JUST CHANGE THIS LINE
ADD app_specific_files/dummyapp30/scripts/ /centralized_scheduler/

ADD jupiter_config.ini /jupiter_config.ini


ADD circe/original/start_worker.sh /start.sh
RUN chmod +x /start.sh

WORKDIR /

# tell the port number the container should expose
EXPOSE 22 57021

# run the command
CMD ["./start.sh"]

