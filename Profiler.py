#!/usr/bin/python
"""This module is for testing and profiling the code only.
   This file should not be included in any release."""

import hotshot
from hotshot import stats

import Jokosher

profile = hotshot.Profile("Jokosher", lineevents=1)
profile.runcall(Jokosher.main)

s = stats.load("Jokosher")

s.strip_dirs()
s.sort_stats("cumulative", "calls").print_stats()
s.sort_stats("time", "calls").print_stats()

