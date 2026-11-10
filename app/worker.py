"""M08/M12 process entry point; one worker is enough for the prototype."""
import logging
import time
from .jobs import run_once
from .exports import deliver

def main():
    logging.basicConfig(level=logging.INFO)
    while True:
        try:
            worked=run_once();deliver()
            if not worked: time.sleep(1)
        except KeyboardInterrupt:
            return
        except Exception:
            logging.exception('worker iteration failed')
            time.sleep(2)

if __name__=='__main__': main()

