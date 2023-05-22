#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
import platform
import time
import logging
import threading
from utils import *
from packet import Packet
from client import Client
from gpt4all import GPT4All

logger = logging.getLogger(__name__)
DEFAULT_NAME = "Alice"
CMD_PREFIX = "#!#CMD_START#!#"
CMD_SUFFIX = "#!#CMD_END#!#"

def new_print(*args, **kwargs):
    return logger.debug(*args, **kwargs)

class Gpt:

    def __init__(self, thread_count:int, agent_settings:dict):
        self.threads = thread_count
        self.settings = agent_settings

        if self.settings["name"] == None:
            self.settings["name"] = DEFAULT_NAME

        thread = threading.Thread(target=self._init, daemon=True)
        thread.start()

        self.local_ip = self._get_local_ip()
        self.public_ip = self._get_public_ip()
        self.history = []
    
    def get_settings(self):
        return self.settings

    def get_status(self):
        return self.status

    def prompt(self, client:Client, context_id:str, input:str):
        thread = threading.Thread(target=self._prompt, args=(client, context_id, input), daemon=True)
        thread.start()

    def _init(self):
        self.status = "initializing"
        model_type = None
        if "model_type" in self.settings:
            model_type = self.settings["model_type"]
        
        self.gpt4all = GPT4All(model_name=self.settings["model"], model_path=None, model_type=model_type)
        self.gpt4all.model.set_thread_count(self.threads)
        self.status = "idle"

    def _prompt(self, client:Client, context_id:str, input:str):

        if self.gpt4all == None:
            client.send(packet=Packet.CHAT, content={
                "success": False,
                "error": "model is not done initializing",
                "sender": self.name,
                "bot": True,
                "type": "text",
                "data": None
            })
            return

        self.status = "processing"
        unix_time = int(time.time())
        current_date = time.strftime("%A %B %d %Y")
        current_time = time.strftime("%H:%M:%S %Z (UTC%z)")
        messages = []
        system_prompt = f"""Your name is {self.settings["name"]}.
You are a LLM model.
Your model file is {self.settings["model"]}.
Your model seed is {self.settings["seed"]}.
The current date is {current_date}.
The current time is {current_time}.
You are running on {sys.platform.title()} {platform.release()}.
The current prompt software is running on Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}.
Your local IP Address is {self.local_ip} and public IP Address is {self.public_ip}.
You have no direct access to the file-system or internet.
gpt4all-box is a gpt4all User Interface and Command-Line Interface service packaged in a containerized environment.
"""

        supplemental_prompt = f"""If the user requests that you:

1. Make a HTTP GET request to a URL.
2. Change your name.

You may do so by responding in the following format,
by first responding with the string `{CMD_PREFIX}`,
then insert a new-line, then write `URL ` (notice the space) and then the URL the user specified.
Or if the user wants you to change your name, instead of `WEB `, write `NAME ` and then the desired
name the user specified. Finally insert a new line, and then write `{CMD_SUFFIX}`
and insert a new-line again. You can then type out your response to the user.
An example of this would look like:

```
{CMD_PREFIX}
URL https://example.com
{CMD_SUFFIX}

I have successfully made a HTTP GET request to [https://example.com](https://example.com).
```

or for a name change to Bob:

```
{CMD_PREFIX}
NAME Bob
{CMD_SUFFIX}
```

My name is now Bob.
"""

        messages.append({
            "role": "system",
            "content": system_prompt
        })
        #messages.append({
        #    "role": "system",
        #    "content": supplemental_prompt
        #})

        #for message in self.history:
        #    messages.append(message)

        messages.append({
            "role": "user",
            "content": input
        })

        ###############################################################
        
        prompt = self._build_prompt(messages)
        print(prompt)

        output = self.gpt4all.generate(
            prompt=prompt,
            # kwargs
            logits_size=self.settings["logits_size"],       # int = 0
            tokens_size=self.settings["tokens_size"],       # int = 0
            n_past=self.settings["n_past"],                 # int = 0, 
            n_ctx=self.settings["n_ctx"],                   # int = 1024, 
            n_predict=self.settings["n_predict"],           # int = 128, 
            top_k=self.settings["top_k"],                   # int = 40, 
            top_p=self.settings["top_p"],                   # float = .9, 
            temp=self.settings["temperature"],              # float = .1, 
            n_batch=self.settings["n_batch"],               # int = 8, 
            repeat_penalty=self.settings["repeat_penalty"], # float = 1.2, 
            repeat_last_n=self.settings["repeat_last_n"],   # int = 10,    last n tokens to penalize
            context_erase=self.settings["context_erase"]    # float = .5,  percent of context to erase if we exceed the context window
        )

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

        self.status = "idle"

        client.send(packet=Packet.CHAT, content={
            "success": True,
            "error": None,
            "sender": self.settings["name"],
            "bot": True,
            "type": "text",
            "data": b64e(output)
        }, context_id=context_id)



    def _build_prompt(self, messages:dict[str]):
        full_prompt = ""

        for message in messages:
            if message["role"] == "system":
                full_prompt += "### System:\n" + message["content"] + "\n"

        
        full_prompt += """### Instruction: 
The prompt below is a question to answer, a task to complete, or a conversation 
to respond to; decide which and write an appropriate response.

### Prompt: \n"""

        for message in messages:
            if message["role"] == "user":
                full_prompt += message["content"] + "\n"
            if message["role"] == "assistant":
                full_prompt += "### Response: " + message["content"] + "\n"

        full_prompt += "### Response: "

        return full_prompt

    def _get_local_ip(self):
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("1.1.1.1", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip

    def _get_public_ip(self):
        import requests
        endpoint = 'https://checkip.amazonaws.com/'
        response = requests.get(endpoint)
        if response.status_code != 200:
            return "0.0.0.0"
        
        return response.text.replace("\n","").strip()