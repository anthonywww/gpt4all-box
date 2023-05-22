#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import uuid
import logging

from packet import Packet

logger = logging.getLogger(__name__)

class Client:

    def __init__(self, wsclient, session=None):
        self.wsclient = wsclient
        self.session = session

        session_string = ""

        if session != None:
            session_string = f" initialized with session id {session.get_id()}"

        logger.debug(f"Client #{self.get_id()} ({self.get_address()}:{self.get_port()}){session_string}")

    def set_session(self, session):
        logger.debug(f"Client #{self.get_id()} ({self.get_address()}:{self.get_port()}) session id updated to {session.get_id()}")
        self.session = session
        session.get_gpt()

    def get_session(self):
        return self.session

    def send(self, packet:Packet, content:dict=None, context_id:str=uuid.uuid4().hex):
        r = {
            "msg": str(packet),
            "cid": context_id,
            "content": content,
        }
        self.send_raw(json.dumps(r))

    def send_raw(self, payload):
        try:
            logger.debug(f"Client #{self.get_id()} ({self.get_address()}:{self.get_port()}) sending packet {str(payload)}")
            self.wsclient["handler"].send_message(payload)
        except BrokenPipeError:
            pass

    def disconnect(self):
        self.wsclient["handler"].send_close(status=1002)

    def get_id(self):
        return self.wsclient["id"]

    def get_address(self):
        return self.wsclient["address"][0]

    def get_port(self):
        return self.wsclient["address"][1]
