#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import sys
import platform
import json
import threading
import logging

from websocket_server import WebsocketServer
from utils import *
from timer import Timer
from packet import Packet
from client import Client
from session import Session

ADDRESS = "0.0.0.0"
PORT = 8184
HEARTBEAT_INTERVAL = 1000 * 5 # 5 seconds
MAX_IDLE_SESSION_DURATION = 1000 * 60 * 3 # 30 minutes
MODEL_THREADS = 4

logger = logging.getLogger(__name__)

class Server():

    def __init__(self, address:str, port:int):
        self.clients = []
        self.sessions = []

        self.motd = os.getenv("SYSTEM_MESSAGE", None)
        self.heartbeat_interval = os.getenv("HEARTBEAT_INTERVAL", HEARTBEAT_INTERVAL)
        self.max_idle_session_duration = os.getenv("MAX_IDLE_SESSION_DURATION", MAX_IDLE_SESSION_DURATION)
        self.model_threads = int(os.getenv("MODEL_THREADS", MODEL_THREADS))
        self.ssl_key = os.getenv("SSL_KEY", None)
        self.ssl_cert = os.getenv("SSL_CERT", None)

        self.server = WebsocketServer(host=address, port=port, loglevel=logging.WARNING, key=self.ssl_key, cert=self.ssl_cert)
        self.server.set_fn_new_client(self.on_connect)
        self.server.set_fn_client_left(self.on_disconnect)
        self.server.set_fn_message_received(self.on_message)

        self.heartbeat = Timer(self._heartbeat, self.heartbeat_interval)

        try:
            if address=="0.0.0.0":
                address = "*"
            logger.info(f"Server listening on {address}:{port} ...")
            self.server.run_forever()
        except KeyboardInterrupt:
            pass

        print("") # get rid of annoying '^C' print
        logger.info(f"Sending shutdown broadcast to all clients ...")
        for c in self.clients:
            c.send(packet=Packet.SYSTEM, content={
                "type": "text",
                "data": b64e("The server is going offline immediately!")
            })
        
        logger.info(f"Shutting down!")
        self.heartbeat.stop()
        self.server.shutdown_gracefully()

    def on_connect(self, client, server):
        client = Client(client)
        logger.info(f"Client #{client.get_id()} ({client.get_address()}:{client.get_port()}) connected")

        if self.motd != None:
            msgs = self.motd.split("|")
            for msg in msgs:
                client.send(packet=Packet.SYSTEM, content={
                    "type": "text",
                    "data": b64e(msg)
                })

        # broadcast to all other clients that this client connected
        #for c in self.clients:
        #    c.send("session_add", {"id": client.get_id(), "address": client.get_address(), "port": client.get_port()})
        
        self.clients.append(client)


    def on_disconnect(self, client, server):

        # Get client from local clients list by its handler id
        for c in self.clients:
            if c.get_id() == client["id"]:
                client = c
                break

        # Instance is already deleted
        if isinstance(client, dict):
            return

        logger.info(f"Client #{client.get_id()} ({client.get_address()}:{client.get_port()}) disconnected")

        self.clients.remove(client)
        del client


    def on_message(self, client, server, message):
        
        # Get client from local clients list by its handler id
        for c in self.clients:
            if c.get_id() == client["id"]:
                client = c
                break

        # Instance is already deleted
        if isinstance(client, dict):
            return

        # Invalid message, disconnect client
        if message == None:
            logger.warning(f"Client #{client.get_id()} ({client.get_address()}:{client.get_port()}) attempted to send NULL data!")
            client.disconnect()
            return
        
        # Invalid non-JSON message, disconnect client
        try:
            msg = json.loads(message)
            logger.debug(f"Client #{client.get_id()} ({client.get_address()}:{client.get_port()}) received packet {message}")


            # Ensure cid (context_id) is set
            if not 'cid' in msg:
                raise Exception("invalid data-type for context_id, must be string")
        
            if not isinstance(msg["cid"], str):
                raise Exception("invalid data-type for context_id, must be string")
            
            if len(msg["cid"]) != 32:
                raise Exception("invalid length for context_id, must be 32")
                


            if (msg["msg"] == Packet.PING):
                client.send(packet=Packet.PING, content=None, context_id=msg["cid"])
            elif (msg["msg"] == Packet.SESSION):
                if msg["content"]["request"] == "create":
                    # Create a new session (expensive...)
                    settings = msg["content"]["settings"]
                    session = Session(self.max_idle_session_duration, self.model_threads, settings)
                    logger.info(f"Client #{client.get_id()} ({client.get_address()}:{client.get_port()}) created a new session {session.get_id()}")
                    self.sessions.append(session)
                    client.set_session(session)
                    client.send(packet=Packet.SESSION, content={
                        "session_id": session.get_id(),
                        "success": True,
                        "error": None
                    }, context_id=msg["cid"])
                elif msg["content"]["request"] == "resume":
                    session = self._get_session(msg["content"]["session_id"])
                    if session == None:
                        client.send(packet=Packet.SESSION, content={
                            "success": False,
                            "error": "expired"
                        }, context_id=msg["cid"])
                    else:
                        client.set_session(session)
                        client.send(packet=Packet.SESSION, content={
                            "success": True,
                            "error": None
                        }, context_id=msg["cid"])
                elif msg["content"]["request"] == "status":
                    session = None
                    for sess in self.sessions:
                        if sess.get_id() == msg["content"]["session_id"]:
                            if sess.has_expired():
                                sess.destroy()
                                client.send(packet=Packet.SESSION, content={
                                    "success": False,
                                    "error": "expired"
                                }, context_id=msg["cid"])
                                return
                            session = sess
                            break
                    if session == None:
                        client.set_session(None)
                        session.destroy()
                        client.send(packet=Packet.SESSION, content={
                            "success": False,
                            "error": "unknown session id"
                        }, context_id=msg["cid"])
                    else:
                        gpt = session.get_gpt()
                        client.send(packet=Packet.SESSION, content={
                            "success": True,
                            "error": None,
                            "status": gpt.get_status(),
                            "settings": gpt.get_settings()
                        }, context_id=msg["cid"])
                elif msg["content"]["request"] == "destroy":
                    # TODO: the user should have a list of sessions it created on initial connection
                    # check if the session_id requested for deletion is in that list, otherwise deny
                    session = client.get_session()
                    if session == None:
                        client.send(packet=Packet.SESSION, content={
                            "success": False,
                            "error": "session does not exist"
                        }, context_id=msg["cid"])
                    else:
                        client.set_session(None)
                        session.destroy()
                        client.send(packet=Packet.SESSION, content={
                            "success": True,
                            "error": None
                        }, context_id=msg["cid"])
                else:
                    raise Exception("invalid session.content.status type")
            elif (msg["msg"] == Packet.CHAT):
                if client.get_session() == None:
                    raise Exception("chat without starting or resuming a session")
                if msg["content"]["type"] != "text":
                    client.send(packet=Packet.CHAT, content={
                            "success": False,
                            "error": "type must be 'text'"
                        }, context_id=msg["cid"])
                else:
                    self._process_chat(client, msg["content"]["data"], msg["cid"])
            else:
                raise Exception("send invalid msg type")

        except json.decoder.JSONDecodeError:
            logger.warning(f"Client #{client.get_id()} ({client.get_address()}:{client.get_port()}) attempted to send bad JSON data")
            client.disconnect()
            return
        except Exception as e:
            err = e
            if hasattr(e, 'message'):
                err = e.message
            logger.warning(f"Client #{client.get_id()} ({client.get_address()}:{client.get_port()}) attempted an invalid action ({err})")
            client.disconnect()
            return

    def _heartbeat(self):
        # Clean-up stale sessions
        stale_sessions = 0
        for session in self.sessions:
            if session.has_expired():
                self.sessions.remove(session)
                stale_sessions += 1
        logger.debug(f"Cleaned up {stale_sessions} stale sessions")

    def _get_session(self, session_id:str):
        for session in self.sessions:
            if session.get_id() == session_id and not session.has_expired():
                return session
        return None

    def _process_chat(self, client:Client, message:str, context_id:str):
        message = b64d(message)

        logger.info(f"Client #{client.get_id()} ({client.get_address()}:{client.get_port()}) prompt: {message}")
        
        gpt = client.get_session().get_gpt()

        # session expired, get a new one
        if gpt == None:
            client.send(packet=Packet.SESSION, content={
                "success": False,
                "error": "expired"
            }, context_id=context_id)
            return

        # Check if an existing job is already running
        if gpt.get_status() == "processing":
            client.send(packet=Packet.CHAT, content={
                "success": False,
                "error": "still processing prior request"
            }, context_id=context_id)
            return

        gpt.prompt(client=client, context_id=context_id, input=message)


if __name__ == '__main__':
    formatter = logging.Formatter(fmt='%(asctime)s [%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    root_logger = logging.getLogger("root")
    root_logger.setLevel(logging.INFO)
    #root_logger.setLevel(logging.DEBUG)
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    Server(ADDRESS, PORT)
