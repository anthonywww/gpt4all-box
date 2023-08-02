#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import uuid
import logging

import session as Session
import packet as Packet

logger = logging.getLogger(__name__)

class Client:

    def __init__(self, wsclient):
        self.wsclient = wsclient
        self.sessions = [] # These are just references to the original object, just as the one in g4ab.py
        logger.debug(f"Client #{self.get_id()} ({self.get_address()}:{self.get_port()} initialized)")

    def add_session(self, session:Session):
        logger.debug(f"Client #{self.get_id()} ({self.get_address()}:{self.get_port()}) bound to session id {session.get_id()}")
        session.get_gpt() # Update session timestamp to prevent it from expiring
        self.sessions.append(session)

    def remove_session(self, session:Session):
        logger.debug(f"Client #{self.get_id()} ({self.get_address()}:{self.get_port()}) unbound from session id {session.get_id()}")
        self.sessions.remove(session)

    def has_session_id(self, session_id:int):
        return not self.get_session_by_id(session_id) == None

    def get_sessions(self):
        sessions = []
        for sess in self.sessions:
            if not sess.has_expired():
                sessions.append(sess)
        return sessions

    def get_session_by_id(self, session_id:str):
        for sess in self.get_sessions():
           if sess.get_id() == session_id:
               return sess
        return None

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
