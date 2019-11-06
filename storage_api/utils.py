"""
This file contains various utilities, including this recipe for an
ordered set http://code.activestate.com/recipes/576694/
"""

import logging
import sys

def init_logger(
    tag = 'SAPI',
    level = logging.INFO,
    line = '%(asctime)s [%(filename)s:%(lineno)d] [%(process)d] %(levelname)s %(name)s %(message)s',
    # We just log to stdout. Service running in a container doesn't have permissions to write to local files
    log_file = '/var/log/sapi.log',
    stdout = True
    ):
    log = logging.getLogger(tag)
    log.setLevel(level)
    dateformat = "%Y-%m-%dT%H:%M:%S%z" # Same format as `date --iso-8601='seconds'`
    formatter = logging.Formatter(fmt=line, datefmt=dateformat)
    #lf = logging.FileHandler(log_file)
    #lf.setFormatter(formatter)
    #log.addHandler(lf)

    if stdout:
        ch = logging.StreamHandler(sys.stdout)
        ch.setFormatter(formatter)
        log.addHandler(ch)

    return log

def dict_without(d, *keys):
    """
    Return a dictionary d, ensuring that keys are absent.
    """
    d2 = d.copy()
    for key in keys:
        d2.pop(key)

    return d2


def filter_none(d):
    """
    Remove items in d that are None.
    """

    return dict_without(d, *filter(lambda k: d[k] is None, d.keys()))


def compose_decorators(*decs):
    """
    Compose a set of decorators into one.

    Suggested by Jochen Ritzel: http://stackoverflow.com/a/5409569
    """
    def deco(f):
        for dec in reversed(decs):
            f = dec(f)
        return f
    return deco


# http://stackoverflow.com/a/26853961
# Waiting for python 3.5 when we can just do z = {**x, **y}
def merge_two_dicts(x, y):
    """
    Given two dicts, merge them into a new dict as a shallow copy,
    keeping keys from y if they are already in x
    """
    z = x.copy()
    z.update(y)
    return z


def pairwise(iterable):
    return zip(iterable[0::2], iterable[1::2])
