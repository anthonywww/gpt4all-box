#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
import platform
import time
import logging
import threading
from packet import Packet
from gpt_status import GPTStatus
from gpt4all import GPT4All
from utils import *

import client as Client

logger = logging.getLogger(__name__)
DEFAULT_NAME = "Alice"
CMD_PREFIX = "#!#CMD_START#!#"
CMD_SUFFIX = "#!#CMD_END#!#"

def new_print(*args, **kwargs):
    return logger.debug(*args, **kwargs)

class Gpt:

    def __init__(self, model_path:str, thread_count:int, agent_settings:dict):
        self.model_path = model_path
        self.model_threads = thread_count
        self.settings = agent_settings
        self.device = "cpu" # 'cpu' 'gpu' 'amd' 'intel' 'nvidia'

        if self.settings["name"] == None:
            self.settings["name"] = DEFAULT_NAME

        self.thread = threading.Thread(target=self._init, daemon=True)
        self.thread.start()

        self.local_ip = self._get_local_ip()
        self.public_ip = self._get_public_ip()
    
    def get_settings(self):
        return self.settings

    def get_status(self):
        return self.status

    def prompt(self, client:Client, session_id:str, context_id:str, input:str):
        if self.get_status() == GPTStatus.INITIALIZING or self.gpt4all == None:
            client.send(packet=Packet.CHAT, content={
                "success": False,
                "session_id": session_id,
                "error": "model is still initializing",
                "sender": self.name,
                "bot": True,
                "type": "text",
                "data": None
            })
            return
        elif self.get_status() == GPTStatus.PROCESSING:
            client.send(packet=Packet.CHAT, content={
                "success": False,
                "session_id": session_id,
                "error": "model is still processing the prior request",
                "sender": self.name,
                "bot": True,
                "type": "text",
                "data": None
            })
            return
        self.thread = threading.Thread(target=self._prompt, args=(client, session_id, context_id, input), daemon=True)
        self.thread.start()

    def _init(self):
        self.status = GPTStatus.INITIALIZING
        model_type = None
        if "model_type" in self.settings:
            model_type = self.settings["model_type"]
        
        self.gpt4all = GPT4All(model_name=self.settings["model"], model_path=self.model_path, model_type=model_type, n_threads=self.model_threads, allow_download=False, device=self.device)
        self.gpt4all.model.set_thread_count(self.model_threads)
        self.status = GPTStatus.IDLE

    def _destroy(self):
        del self.gpt4all

    def _prompt(self, client:Client, session_id:str, context_id:str, input:str):
        self.status = GPTStatus.PROCESSING
        unix_time = int(time.time())
        current_date = time.strftime("%A %B %d %Y")
        current_time = time.strftime("%H:%M:%S %Z (UTC%z)")
        messages = []
        system_prompt = f"""You are {self.settings["name"]}, a fully-capable Large Language Model personal assistant that can help with virtually anything.
Your model file is {self.settings["model"]}.
Your model seed is {self.settings["seed"]}.
The current date is {current_date}.
The current time is {current_time}.
You are running on {sys.platform.title()} {platform.release()}.
Your local IP Address is {self.local_ip} and public IP Address is {self.public_ip}.
For tabular information return it in Markdown format, do not return HTML.
"""
        
        # gpt4all-box is a gpt4all User Interface and Command-Line Interface service packaged in a containerized environment.

        messages.append({
            "role": "system",
            "content": system_prompt
        })

        messages.append({
            "role": "user",
            "content": input
        })

        ###############################################################
        
        prompt = self._build_prompt(messages)

        logging.getLogger("gpt4all.pyllmodel").setLevel(logging.CRITICAL)

        output = self.gpt4all.generate(
            prompt=prompt,
            streaming=False,
            # kwargs
            max_tokens=self.settings["max_tokens"],         # int = 128,  formerly n_predict
            top_k=self.settings["top_k"],                   # int = 40, 
            top_p=self.settings["top_p"],                   # float = .9, 
            temp=self.settings["temperature"],              # float = .1, 
            n_batch=self.settings["n_batch"],               # int = 8, 
            repeat_penalty=self.settings["repeat_penalty"], # float = 1.2, 
            repeat_last_n=self.settings["repeat_last_n"],   # int = 10,    last n tokens to penalize
        )

        """
        self.history.append({
            "time": unix_time,
            "role": "user",
            "content": input
        })

        self.history.append({
            "time": int(time.time()),
            "role": "assistant",
            "content": output
        })
        """

        self.status = GPTStatus.IDLE

        client.send(packet=Packet.CHAT, content={
            "success": True,
            "session_id": session_id,
            "error": None,
            "sender": self.settings["name"],
            "bot": True,
            "type": "text",
            "data": b64e(output)
        }, context_id=context_id)



    def _build_prompt(self, messages:dict[str]) -> str:
        full_prompt = ""

        for message in messages:
            if message["role"] == "system":
                full_prompt += "### System:\n" + message["content"] + "\n"

        
        full_prompt += """### Instruction: 
The prompt below is a question to answer, a task to complete, or a conversation 
to respond to; decide which and write a response.

### Prompt: \n"""

        for message in messages:
            if message["role"] == "user":
                full_prompt += message["content"] + "\n"
            if message["role"] == "assistant":
                full_prompt += "### Response: " + message["content"] + "\n"

        full_prompt += "### Response: "

        return full_prompt

    def _get_local_ip(self) -> str:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("1.1.1.1", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip

    def _get_public_ip(self) -> str:
        import requests
        endpoint = 'https://checkip.amazonaws.com/'
        response = requests.get(endpoint)
        if response.status_code != 200:
            return "0.0.0.0"
        
        return response.text.replace("\n","").strip()