import os
import sys
import queue
import threading
import logging
import time
import string
import random

logging.basicConfig(format="%(levelname)s:%(filename)s:%(message)s")
log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

try:
    # successful if running in container
    sys.path.append("/jupiter/build")
    from jupiter_utils import app_config_parser
except ModuleNotFoundError:
    # Python file must be running locally for testing
    sys.path.append("../../core/")
    from jupiter_utils import app_config_parser

# Jupiter executes task scripts from many contexts. Instead of relative paths
# in your code, reference your entire app directory using your base script's
# location.
APP_DIR = os.path.dirname(os.path.abspath(__file__))

# Parse app_config.yaml. Keep as a global to use in your app code.
app_config = app_config_parser.AppConfig(APP_DIR)


def random_string():
    letters = string.ascii_letters + string.digits
    s = [random.choice(letters) for i in range(6)]
    return ''.join(s)


# Run by dispatcher (e.g. CIRCE). Custom tasks are unable to receive files
# even though a queue is setup. Custom tasks can, however, send files to any
# DAG task.
def task(q, pathin, pathout, task_name):
    log.info(f"Starting non-DAG task {task_name}")
    children = app_config.child_tasks(task_name)
    log.info(f"My children are {children}")

    # if this acts as a data soruce, you can send files to a DAG task
    for child in children:
        fname = f"{task_name}_{child}_fake-{random_string()}"
        fname = os.path.join(pathout, fname)
        with open(fname, "w") as f:
            f.write("This is a fake input file of 43 characters.")

        log.info(f"created {fname}")

    while True:
        time.sleep(999)

    log.error("ERROR: should never reach this")


if __name__ == '__main__':
    # Testing Only
    q = queue.Queue()
    log.info("Threads will run indefintely. Hit Ctrl+c to stop.")
    t = threading.Thread(target=task, args=(q, "./", "./", "test"))
    t.start()
