"""Allow ``python -m diskgoup``."""

import multiprocessing

# A worker of a pool of processes starts this program again. A frozen build
# has to hand itself over to the worker before it imports anything, so that
# the worker does not pay for the whole command line.
multiprocessing.freeze_support()

from diskgoup.cli import run  # noqa: E402

if __name__ == "__main__":
    run()
