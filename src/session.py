#!/usr/bin/env python
# -*- coding: utf-8 -*-
import time
import uuid
import logging
import random
from gpt import Gpt
from typing import Union

logger = logging.getLogger(__name__)

class Session:

    def __init__(self, max_idle_session_duration:int, model_path:str, model_threads:int, model_settings:dict=None):
        # TODO: possibly store the ip addr of who created this session, that way it can be rate-limited by ip addr

        self.max_idle_session_duration = max_idle_session_duration
        self.model_path = model_path
        self.model_threads = model_threads

        """
        max_tokens     =self.settings["max_tokens"],         # int = 128,  formerly, n_predict
        top_k          =self.settings["top_k"],             # int = 40, 
        top_p          =self.settings["top_p"],             # float = .9, 
        temp           =self.settings["temperature"],       # float = .1, 
        n_batch        =self.settings["n_batch"],           # int = 8, 
        repeat_penalty =self.settings["repeat_penalty"],    # float = 1.2, 
        repeat_last_n  =self.settings["repeat_last_n"],     # int = 10,    last n tokens to penalize
        context_erase  =self.settings["context_erase"]      # float = .5,  percent of context to erase if we exceed the context window
        """

        default_model_settings = {
            "model": "mistral-7b-openorca.Q4_0.gguf",
            "name": None,
            "seed": random.randint(-2147483647, 2147483647),
            "max_tokens": 200,
            "top_k": 40,
            "top_p": 0.9,
            "temperature": 0.1,
            "n_batch": 8,
            "repeat_penalty": 1.2,
            "repeat_last_n": 64
        }

        self.model_settings = default_model_settings

        for k in default_model_settings:
            if k in model_settings:
                value = model_settings[k]

                # integers
                if k == "n_batch" or k == "top_k" or k == "repeat_last_n" or k == "max_tokens":
                    value = int(value)
        
                # floats
                if k == "temperature" or k == "top_p" or k == "repeat_penalty":
                    value = float(value)

                # string or other, just set it
                self.model_settings[k] = value


        self.id = uuid.uuid4().hex
        logger.debug(f"Creating new session id {self.id} ...")
        self.gpt = Gpt(self.model_path, self.model_threads, self.model_settings)
        self.last_used = int(time.time())
        logger.debug(f"Session id {self.id} created! Valid for {max_idle_session_duration} seconds")

    def get_id(self) -> str:
        return self.id

    def reload(self):
        self.last_used = int(time.time())

    def get_gpt(self) -> Union[Gpt, None]:
        
        if self.has_expired():
            return None
        
        self.reload()
        return self.gpt

    def get_expiration(self):
        #current_time = int(time.time())
        return self.last_used + self.max_idle_session_duration

    def has_expired(self) -> bool:
        current_time = int(time.time())

        if current_time > self.get_expiration():
            self.destroy()
            return True

        return False

    def destroy(self):
        del self.gpt

    def get_last_used(self) -> int:
        return self.last_used
