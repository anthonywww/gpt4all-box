#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import sys
import platform
import json
import threading
import requests
import hashlib
import logging
import traceback

from websocket_server import WebsocketServer
from utils import *
from timer import Timer
from packet import Packet
from gpt_status import GPTStatus
from client import Client
from session import Session

ADDRESS = "0.0.0.0"
PORT = 8184
HEARTBEAT_INTERVAL = 1000 * 5 # 5 seconds
MAX_IDLE_SESSION_DURATION = 1000 * 60 * 3 # 30 minutes
MODEL_THREADS = 4
MODEL_DOWNLOADS = "https://gpt4all.io/models"

logger = logging.getLogger(__name__)

class Server():

    def __init__(self, address:str, port:int):
        self.models = []
        self.clients = []
        self.sessions = []
        self.gpt_ready = False

        self.motd = os.getenv("SYSTEM_MESSAGE", None)
        self.heartbeat_interval = os.getenv("HEARTBEAT_INTERVAL", HEARTBEAT_INTERVAL)
        self.max_idle_session_duration = os.getenv("MAX_IDLE_SESSION_DURATION", MAX_IDLE_SESSION_DURATION)
        self.model_threads = int(os.getenv("MODEL_THREADS", MODEL_THREADS))
        self.model_downloads = os.getenv("MODEL_DOWNLOADS", MODEL_DOWNLOADS)
        self.model_path = os.getenv("MODEL_PATH", "./models/")

        thread = threading.Thread(target=self._check_models, args=(), daemon=True)
        thread.start()

        self.server = WebsocketServer(host=address, port=port, loglevel=logging.WARNING)
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

        # If the message of the day exists, send it as a system message!
        if self.motd != None:
            msgs = self.motd.split("|")
            for msg in msgs:
                client.send(packet=Packet.SYSTEM, content={
                    "type": "message",
                    "data": b64e(msg)
                })

        # Automatically send the client a list of models this server supports.
        client.send(packet=Packet.SYSTEM, content={
            "type": "models",
            "data": self.models
        })

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
            


            elif (msg["msg"] == Packet.SYSTEM):
                if msg["content"] == None:
                     raise Exception("system.content is null")
                if not msg["content"]["request"] == "models":
                    raise Exception("invalid system.content.request type")
                logger.debug(f"Client #{client.get_id()} ({client.get_address()}:{client.get_port()}) requested supported model list")
                client.send(packet=Packet.SYSTEM, content={
                    "models": self.models,
                    "success": True,
                    "error": None
                }, context_id=msg["cid"])
            
            
            
            elif (msg["msg"] == Packet.SESSION):
                if msg["content"] == None:
                     raise Exception("session.content is null")
                if msg["content"]["request"] == "create":
                    settings = msg["content"]["settings"]
                    session = Session(self.max_idle_session_duration, self.model_path, self.model_threads, settings)
                    logger.info(f"Client #{client.get_id()} ({client.get_address()}:{client.get_port()}) created a new session {session.get_id()}")
                    self.sessions.append(session)
                    client.add_session(session)
                    client.send(packet=Packet.SESSION, content={
                        "session_id": session.get_id(),
                        "expires": session.get_expiration(),
                        "success": True,
                        "error": None
                    }, context_id=msg["cid"])
                elif msg["content"]["request"] == "resume":
                    session_id = msg["content"]["session_id"]
                    if client.has_session_id(session_id):
                        session = client.get_session_by_id(session_id)
                        session.reload()
                        client.send(packet=Packet.SESSION, content={
                            "expires": session.get_expiration(),
                            "success": True,
                            "error": None
                        }, context_id=msg["cid"])
                        return
                    session = self._get_session_by_id(session_id)
                    if session == None:
                        client.send(packet=Packet.SESSION, content={
                            "success": False,
                            "error": "expired"
                        }, context_id=msg["cid"])
                        return
                    session.reload()
                    self.sessions.append(session)
                    client.add_session(session)
                    client.send(packet=Packet.SESSION, content={
                        "expires": session.get_expiration(),
                        "success": True,
                        "error": None
                    }, context_id=msg["cid"])
                elif msg["content"]["request"] == "status":
                    session = client.get_session_by_id(msg["content"]["session_id"])
                    if session == None:
                        client.set_session(None)
                        session.destroy()
                        client.send(packet=Packet.SESSION, content={
                            "success": False,
                            "error": "expired"
                        }, context_id=msg["cid"])
                        return
                    gpt = session.get_gpt()
                    client.send(packet=Packet.SESSION, content={
                        "last_used": session.get_last_used(),
                        "expires": session.get_expiration(),
                        "status": gpt.get_status(),
                        "settings": gpt.get_settings(),
                        "success": True,
                        "error": None
                    }, context_id=msg["cid"])
                elif msg["content"]["request"] == "destroy":
                    if msg["content"] == None:
                        raise Exception("session.content is null")
                    if not msg["content"]["session_id"]:
                        raise Exception("session.content.session_id is null")
                    session = client.get_session_by_id(msg["content"]["session_id"])
                    if session == None:
                        client.send(packet=Packet.SESSION, content={
                            "success": False,
                            "error": "not found"
                        }, context_id=msg["cid"])
                        return
                    
                    self.sessions.remove(session)
                    client.remove_session(session)
                    session.destroy()
                    client.send(packet=Packet.SESSION, content={
                        "success": True,
                        "error": None
                    }, context_id=msg["cid"])
                else:
                    raise Exception("invalid session.content.request type")
            
            
            
            elif (msg["msg"] == Packet.CHAT):
                if len(client.get_sessions()) == 0:
                    raise Exception("chat without starting or resuming a session")
                if msg["content"]["type"] != "text":
                    raise Exception("'content.type' must be 'text'")
                if not msg["content"]["session_id"]:
                     raise Exception("missing 'session_id' from 'content'")
                self._process_chat(client, msg["content"]["session_id"], msg["content"]["data"], msg["cid"])
            
            
            
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
            traceback.print_exc()
            client.disconnect()
            return

    def _heartbeat(self):
        # Clean-up stale sessions
        stale_sessions = 0
        for session in self.sessions:
            if session.has_expired():
                self.sessions.remove(session)
                session.destroy()
                del session
                stale_sessions += 1
        logger.debug(f"Cleaned up {stale_sessions} stale sessions")

    def _get_session_by_id(self, session_id:str):
        for session in self.sessions:
            if session.get_id() == session_id and not session.has_expired():
                return session
        return None

    def _process_chat(self, client:Client, session_id:str, message:str, context_id:str):
        message = b64d(message)

        logger.info(f"Client #{client.get_id()} ({client.get_address()}:{client.get_port()}) session id {session_id} prompt: {message}")
        
        if not self.gpt_ready:
            client.send(packet=Packet.CHAT, content={
                "success": False,
                "error": "initializing models"
            }, context_id=context_id)
            client.send(packet=Packet.SYSTEM, content={
                "type": "message",
                "data": b64e("The server is still initializing or downloading models, please try again soon.")
            })
            return

        # Get session by its id
        session = self._get_session_by_id(session_id)

        # session expired?
        if session == None:
            client.send(packet=Packet.SESSION, content={
                "success": False,
                "error": "expired"
            }, context_id=context_id)
            return

        # ensure this session is owned by the client making this request
        if not client.has_session_id(session_id):
            client.send(packet=Packet.SESSION, content={
                "success": False,
                "error": "fraud"
            }, context_id=context_id)
            return

        gpt = session.get_gpt()

        # Check if an existing job is already running
        if gpt.get_status() == GPTStatus.PROCESSING:
            client.send(packet=Packet.CHAT, content={
                "success": False,
                "error": "still processing prior request"
            }, context_id=context_id)
            return

        gpt.prompt(client=client, context_id=context_id, input=message)


    def _download_model(self, filename):

        if "model_list" in self:
            r = requests.get(self.model_downloads)
            
            if not r.status_code == 200 and not r.status_code == 304:
                logger.error(f"Failed to get model list {self.model_downloads}: HTTP Status {r.status_code}")
                return
           
            json_content = r.json()



    def _check_models(self):
        if not os.path.exists(self.model_path):
            os.makedirs(self.model_path)
        else:
            if os.path.isfile(self.model_path):
                os.remove(self.model_path)
                os.makedirs(self.model_path)

        if not os.path.isfile(self.model_path + "/models.json"):
            fp = open(self.model_path + "/models.json", 'x')
            fp.write("[]")
            fp.close()

        try:
            fp = open(self.model_path + "/models.json", 'r')
            content = fp.read()
            fp.close()

            json_content = [json.loads(content)]
            
            # Get from service endpoint
            r = requests.get(self.model_downloads + "/models.json")
            json_service = None

            if not r.status_code == 200 and not r.status == 304:
                logger.warning("Failed to fetch {self.model_downloads}/models.json!")
            else:
                json_service = r.json()

                # Populate the models.json with defaults
                if len(json_content) == 0:
                    for service_model in json_service:
                        
                        json_content.append({
                            "name": service_model["name"],
                            "file": service_model["filename"],
                            "hash": service_model["md5sum"],
                            "mem_gb": service_model["ramrequired"],
                            "parameters": service_model["parameters"],
                            "type": service_model["type"],
                            "description": service_model["description"]
                        })

                    fp = open(self.model_path + "/models.json", 'w')
                    fp.write(json.dumps(json_content))
                    fp.flush()
                    fp.close()


            for model in json_content:
                
                valid = False

                # Check the file hash against what was downloaded
                if os.path.isfile("{self.model_path}/{model.file}"):
                    file_hash = hashlib.md5(open("{self.model_path}/{model.file}", "rb").read()).hexdigest()
                    expected_hash = model["hash"]
                    if file_hash == expected_hash:
                        valid = True

                # Check if the file exists, if not download it
                if not os.path.isfile("{self.model_path}/{model.file}") and valid:
                    logger.info("Downloading model {model.file} ...")
                    response = requests.get("{self.model_downloads}/{model.file}", stream=True)
                    with open("{self.model_path}/{model.file}", "wb") as f:
                        for chunk in response.iter_content(chunk_size=16 * 1024):
                            f.write(chunk)
                        f.flush()
                        file_hash = hashlib.md5(open("{self.model_path}/{model.file}", "rb").read()).hexdigest()
                        expected_hash = model["hash"]
                        if not file_hash == expected_hash:
                            raise Exception("Hash verification failed for model {model.file}: expected {expected_hash}")

            """
            for service_model in json_service:
                for model in json_content:

                    if "file" in model and "md5sum" in model:
                        if model["file"] == service_model["filename"]:
                            if not model["md5sum"] == service_model["md5sum"]:
                                # hashes do not match, replace our entry with the service's entry
                                pass

                if not service_model["filename"] in json_content:
                    json_content.append({
                        "hash": service_model
                    })

            for model in json_content:
                print(model)
                if not "md5sum" in model or not "filename" in model or not "description" in model:
                    raise Exception()
                
                # Check if the file exists
                model_file_name = model["filename"]
                if not os.path.isfile("{self.model_path}/{model_file_name}"):
                    response = requests.get("{self.model_downloads}/{model_file_name}", stream=True)

                    with open(model_file_name, "wb") as f:
                        for chunk in response.iter_content(chunk_size=16 * 1024):
                            f.write(chunk)
                        f.flush()
                    
                    hash = hashlib.md5(f.read()).hexdigest()
            """

            if len(json_content) == 0:
                raise Exception("No models to load!")


        except:
            logger.error("error parsing models.json:")
            traceback.print_exc()
            pass


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
