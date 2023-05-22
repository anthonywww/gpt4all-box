#!/usr/bin/env python
# -*- coding: utf-8 -*-
from time import sleep
from typing import Callable
from threading import Thread, Event

# StoppableThread is from user Dolphin, from http://stackoverflow.com/questions/5849484/how-to-exit-a-multithreaded-program
class _StoppableThread(Thread):  

    def __init__(self):
        Thread.__init__(self)
        self.stop_event = Event()        

    def stop(self):
        if self.is_alive() == True:
            # set event to signal thread to terminate
            self.stop_event.set()
            # block calling thread until thread really has terminated
            self.join()

class Timer(_StoppableThread):

    def __init__(self, worker_func:Callable, interval:int):
        super().__init__()
        self._interval = interval
        self._worker_func = worker_func

    def run(self):
        while not self.stop_event.is_set():
            self._worker_func()
            sleep(self._interval)