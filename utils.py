"""
This file contains various utilities, including this recipe for an
ordered set http://code.activestate.com/recipes/576694/
"""
import collections


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
