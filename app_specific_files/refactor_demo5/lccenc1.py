import os
import shutil
import sys
import queue
import threading
import logging
import glob
import time
import json


classlist = ['fireengine', 'schoolbus', 'whitewolf', 'hyena', 'tiger', 'kitfox', 'persiancat', 'leopard', 'lion',  'americanblackbear', 'mongoose', 'zebra', 'hog', 'hippopotamus', 'ox', 'waterbuffalo', 'ram', 'impala', 'arabiancamel', 'otter']
classids = np.arange(0,len(classlist),1)
classmap = dict(zip(classlist, classids))


logging.basicConfig(format="%(levelname)s:%(filename)s:%(message)s")
log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

try:
    # successful if running in container
    sys.path.append("/jupiter/build")
    from jupiter_utils import app_config_parser
except ModuleNotFoundError:
    # Python file must be running locally for testing
    sys.path.append("../../mulhome_scripts/")
    from jupiter_utils import app_config_parser

# Jupiter executes task scripts from many contexts. Instead of relative paths
# in your code, reference your entire app directory using your base script's
# location.
APP_DIR = os.path.dirname(os.path.abspath(__file__))

# Parse app_config.yaml. Keep as a global to use in your app code.
app_config = app_config_parser.AppConfig(APP_DIR, "refactor_demo5")

#task config information
JUPITER_CONFIG_INI_PATH = '/jupiter/build/jupiter_config.ini'
config = configparser.ConfigParser()
config.read(JUPITER_CONFIG_INI_PATH)

def gen_Lagrange_coeffs(alpha_s,beta_s):
    U = np.zeros((len(alpha_s), len(beta_s)))
    for i in range(len(alpha_s)):
        for j in range(len(beta_s)):
            cur_beta = beta_s[j];
            den = np.prod([cur_beta - o   for o in beta_s if cur_beta != o])
            num = np.prod([alpha_s[i] - o for o in beta_s if cur_beta != o])
            U[i][j] = num/den 
    return U


def LCC_encoding(X,N,M):
    w,l = X[0].shape
    n_beta = M
    beta_s, alpha_s = range(1,1+n_beta), range(1+n_beta,N+1+n_beta)

    U = gen_Lagrange_coeffs(alpha_s,beta_s)
    X_LCC = []
    for i in range(N):
        X_zero = np.zeros(X[0].shape)
        for j in range(M):
            X_zero = X_zero + U[i][j]*X[j]
        X_LCC.append(X_zero)
    return X_LCC


# Run by dispatcher (e.g. CIRCE). Use task_name to differentiate the tasks by
# name to reuse one base task file.
def task(q, pathin, pathout, task_name):
    children = app_config.child_tasks(task_name)
    classnum = task_name.split('lccenc')[1]
    classname = classlist[int(classnum)-1]

    input_file = q.get()
    start = time.time()
    src_task, this_task, base_fname = input_file.split("_", maxsplit=3)
    log.info(f"{task_name}: file rcvd from {src_task}")

    # Process the file (this example just passes along the file as-is)
    # Once a file is copied to the `pathout` folder, CIRCE will inspect the
    # filename and pass the file to the next task.

    src = os.path.join(pathin, input_file)
    # dst_task = children[cnt % len(children)]  # round robin selection
    # dst = os.path.join(pathout, f"{task_name}_{dst_task}_{base_fname}")
    # shutil.copyfile(src, dst)



    #LCCENC CODE
    fileid = [x.split('.')[0].split('_')[-1].split('img')[0] for x in filelist]
    logging.debug(fileid)
    classname = [x.split('.')[0].split('img')[1] for x in filelist]
    classid = [classmap[x] for x in classname]
    filesuffixlist = []
    for x,y in zip(classid, fileid):
        tmp = str(x)+'#'+y
        filesuffixlist.append(tmp)
    filesuffix = '-'.join(filesuffixlist)
    logging.debug(filesuffix)

    hdr = {
            'Content-Type': 'application/json',
            'Authorization': None #not using HTTP secure
                                }
    # message for requesting job_id
    # payload = {'event': 'request id'}
    payload = {'class_image': int(classnum)}
    # address of flask server for class1 is 0.0.0.0:5000 and "post-id" is for requesting id
    try:
        # url = "http://0.0.0.0:5000/post-id"
        global_info_ip = os.environ['GLOBAL_IP']
        url = "http://%s:%s/post-id"%(global_info_ip,str(FLASK_SVC))
        print(url)
        # request job_id

        response = requests.post(url, headers = hdr, data = json.dumps(payload))
        job_id = response.json()
        print(job_id)
    except Exception as e:
        print('Possibly running on the execution profiler')
        print(e)
        job_id = 2

    # Parameters
    # L = 10 # Number of images in a data-batch
    L = 2 # Number of images in a data-batch
    M = 2 # Number of data-batches
    N = 3 # Number of workers (encoded data-batches)
    
    # Dimension of resized image
    width = 400
    height = 400
    dim = (width, height)
    
    if FLAG_PART2: #Coding Version
        #Read M batches
        Image_Batch = []
        count_file = 0
        for j in range(M):
            count = 0
            while count < L:
                logging.debug(count_file)
                logging.debug(os.path.join(pathin, filelist[count_file]))
                img = cv2.imread(os.path.join(pathin, filelist[count_file])) 
                if img is not None:
                # resize image
                    img = cv2.resize(img, dim, interpolation = cv2.INTER_AREA)
                    img = np.float64(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)) 
                    img -= img.mean()
                    img /= img.std()
                    img_w ,img_l = img.shape
                    img = img.reshape(1,img_w*img_l)
                    if count == 0:
                       Images = img
                    else:
                       Images = np.concatenate((Images,img), axis=0)  
                    count+=1
                count_file+=1
            Image_Batch.append(Images)

        # Encode M data batches to N encoded data
        En_Image_Batch = LCC_encoding(Image_Batch,N,M)

        out_list = []

        # Save each encoded data-batch i to a csv 
        for i in range(N):
            #destination = os.path.join(pathout,'lccenc'+classnum+'_score'+classnum+chr(i+97)+'_'+'job'+str(job_id)+'.csv')
            destination = os.path.join(pathout,'lccenc'+classnum+'_score'+classnum+chr(i+97)+'_'+'job'+str(job_id)+'_'+filesuffix+'.csv')
            np.savetxt(destination, En_Image_Batch[i], delimiter=',')
            out_list.append(destination)
        
        from_task = '_storeclass'+classnum
        send_runtime_stats('rt_finish_task', destination,from_task)

        
        return out_list
    
    else: # Uncoding version
        #Read M batches
        Image_Batch = []
        count_file = 0
        for j in range(N):
            count = 0
            while count < L:
                logging.debug(count_file)
                img = cv2.imread(os.path.join(pathin, filelist[count_file])) 
                if img is not None:
                # resize image
                    img = cv2.resize(img, dim, interpolation = cv2.INTER_AREA)
                    img = np.float64(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)) 
                    img -= img.mean()
                    img /= img.std()
                    img_w ,img_l = img.shape
                    img = img.reshape(1,img_w*img_l)
                    if count == 0:
                       Images = img
                    else:
                       Images = np.concatenate((Images,img), axis=0)  
                    count+=1
                count_file+=1
            Image_Batch.append(Images)

        En_Image_Batch = LCC_encoding(Image_Batch,N,N)

    dst_task = children # only 1 child
    for i in range(N):
        job = 'job'+str(job_id)
        dst = os.path.join(pathout, f"{task_name}_{dst_task}_{job}_{base_fname}")
        np.savetxt(dst, En_Image_Batch[i], delimiter=',')

    # read the generate output
    # based on that determine sleep and number of bytes in output file
    end = time.time()
    runtime_stat = {
        "task_name" : task_name,
        "start" : start,
        "end" : end
    }
    log.warning(json.dumps(runtime_stat))
    q.task_done()

    log.error("ERROR: should never reach this")


# Run by execution profiler
def profile_execution(task_name):
    q = queue.Queue()
    input_dir = f"{APP_DIR}/sample_inputs/"
    output_dir = f"{APP_DIR}/sample_outputs/"

    # manually add the src (parent) and dst (this task) prefix to the filename
    # here to illustrate how Jupiter will enact this under the hood. the actual
    # src (or parent) is not needed for profiling execution so we fake it here.
    for file in os.listdir(input_dir):
        # skip filse made by other threads when testing locally
        if file.startswith("EXECPROFILER_") is True:
            continue

        # create an input for each child of this task
        for cnt in range(len(app_config.child_tasks(task_name))):
            new = f"{input_dir}/EXECPROFILER{cnt}_{task_name}_{file}"
            shutil.copyfile(os.path.join(input_dir, file), new)

    os.makedirs(output_dir, exist_ok=True)
    t = threading.Thread(target=task, args=(q, input_dir, output_dir, task_name))
    t.start()

    for file in os.listdir(input_dir):
        try:
            src_task, dst_task, base_fname = file.split("_", maxsplit=3)
        except ValueError:
            # file is not in the correct format
            continue

        if dst_task.startswith(task_name):
            q.put(file)
    q.join()

    # clean up input files
    files = glob.glob(f"{input_dir}/EXECPROFILER*_{dst_task}*")
    for f in files:
        os.remove(f)

    # execution profiler needs the name of ouput files to analyze sizes
    output_files = []
    for file in os.listdir(output_dir):
        if file.startswith(task_name):
            output_files.append(file)

    return output_dir, output_files


if __name__ == '__main__':
    # Testing Only
    log.info("Threads will run indefintely. Hit Ctrl+c to stop.")
    for dag_task in app_config.get_dag_tasks():
        log.debug(profile_execution(dag_task['name']))