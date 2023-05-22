#!/usr/bin/env python
# -*- coding: utf-8 -*-
import time
import uuid
import logging
import random
from gpt import Gpt

logger = logging.getLogger(__name__)

class Session:

    def __init__(self, max_idle_session_duration:int, model_threads:int, model_settings:dict=None):
        # TODO: possibly store the ip addr of who created this session, that way it can be rate-limited by ip addr

        self.max_idle_session_duration = max_idle_session_duration
        self.model_threads = model_threads

        """
        logits_size    =self.settings["logits_size"],       # int = 0
        tokens_size    =self.settings["tokens_size"],       # int = 0
        n_past         =self.settings["n_past"],            # int = 0, 
        n_ctx          =self.settings["n_ctx"],             # int = 1024, 
        n_predict      =self.settings["n_predict"],         # int = 128, 
        top_k          =self.settings["top_k"],             # int = 40, 
        top_p          =self.settings["top_p"],             # float = .9, 
        temp           =self.settings["temperature"],       # float = .1, 
        n_batch        =self.settings["n_batch"],           # int = 8, 
        repeat_penalty =self.settings["repeat_penalty"],    # float = 1.2, 
        repeat_last_n  =self.settings["repeat_last_n"],     # int = 10,    last n tokens to penalize
        context_erase  =self.settings["context_erase"]      # float = .5,  percent of context to erase if we exceed the context window
        """

        default_model_settings = {
            "model": "ggml-gpt4all-l13b-snoozy.bin",
            "name": None,
            "seed": random.randint(-2147483647, 2147483647),
            "logits_size": 0,
            "tokens_size": 0,
            "n_past": 0,
            "n_ctx": 2048,
            "n_predict": 128,
            "top_k": 40,
            "top_p": 0.9,
            "temperature": 0.1,
            "n_batch": 8,
            "repeat_penalty": 1.2,
            "repeat_last_n": 10,
            "context_erase": 0.5
        }

        self.model_settings = default_model_settings

        for k in default_model_settings:
            if k in model_settings:
                self.model_settings[k] = model_settings[k]
        
        self.id = uuid.uuid4().hex
        logger.debug(f"Creating new session id {self.id} ...")
        self.gpt = Gpt(self.model_threads, self.model_settings)
        self.last_used = int(time.time())
        logger.debug(f"Session id {self.id} created! Valid for {max_idle_session_duration} seconds")

    def get_id(self):
        return self.id

    def get_gpt(self):
        if self.has_expired():
            return None
        self.last_used = int(time.time())
        return self.gpt

    def has_expired(self):
        current = int(time.time())

        if current - self.last_used > self.max_idle_session_duration:
            self.destroy()
            return True

        return False

    def destroy(self):
        del self.gpt

    def get_last_used(self):
        return self.last_used
