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

from bs4 import BeautifulSoup
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
MODEL_DOWNLOADS = "https://raw.githubusercontent.com/nomic-ai/gpt4all/main/gpt4all-chat/metadata/models2.json"

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
        self.skip_integrity_check = os.getenv("SKIP_INTEGRITY_CHECK", False)

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
                "type": "message",
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
        if self.gpt_ready:
            self._send_models(client)

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

        # TODO: check if session id is valid

        logger.info(f"Client #{client.get_id()} ({client.get_address()}:{client.get_port()}) session id {session_id} prompt: {message}")
        
        if not self.gpt_ready:
            client.send(packet=Packet.CHAT, content={
                "success": False,
                "session_id": session_id,
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
                "session_id": session_id,
                "error": "still processing prior request"
            }, context_id=context_id)
            return

        gpt.prompt(client=client, session_id=session_id, context_id=context_id, input=message)


    def _send_models(self, client:Client) -> None:
        if not client.has_sent_models():
            client.send(packet=Packet.SYSTEM, content={
                    "type": "models",
                    "data": self.models
                })
            client.set_has_sent_models(True)


    """
    This function is actually quite slow because it's single-threaded.
    Unlike if this were re-written in Java we could make use of multi-threaded xxhash.
    """
    def _check_hash(self, filename:str, expected_hash:str) -> bool:
        if os.path.isfile(f"{self.model_path}/{filename}"):
            #file_hash = hashlib.md5(open(f"{self.model_path}/{filename}", "rb").read()).hexdigest()
            md5 = hashlib.md5()
            
            with open(f"{self.model_path}/{filename}", "rb") as f:
                while True:
                    buf = f.read(2**18)
                    if not buf:
                        break
                    md5.update(buf)

            file_hash = md5.hexdigest()

            if file_hash == expected_hash:
                return True        
        return False


    def _download_model(self, url:str, filename:str) -> bool:

        logger.info(f"Downloading model ({filename}) from {url} ...")

        retry_count = 0
        
        while retry_count <= 3:
            try:
                response = requests.get(url, stream=True)

                if not response.status_code == 200 and not response.status_code == 304:
                    logger.error(f"Failed to get model list {self.model_downloads}: HTTP Status {response.status_code}")
                    return False
                
                with open(f"{self.model_path}/{filename}", "wb") as f:
                    for chunk in response.iter_content(chunk_size=16 * 1024):
                        f.write(chunk)
                    f.close()

                return True
            except:
                logger.warning(f"Download for model {url} failed, retrying ...")
                retry_count = retry_count + 1
                pass
        
        logger.error(f"Tried downloading model {url} 3-times and failed.")
        return False


    def _check_models(self) -> None:
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

            json_content = json.loads(content)
            
            # Populate the models.json with defaults
            if len(json_content) == 0:

                # Get from service endpoint
                logger.info(f"Empty models.json, downloading latest models from {self.model_downloads} ...")
                r = requests.get(self.model_downloads)

                if not r.status_code == 200 and not r.status == 304:
                    raise Exception(f"Failed to fetch {self.model_downloads}!")
                
                json_service = r.json()

                for service_model in json_service:

                    filename = service_model["filename"]
                    html_desc = BeautifulSoup(service_model["description"], features="html.parser")
                    url = f"{self.model_downloads}/{filename}"

                    if "url" in service_model:
                        url = service_model["url"]

                    json_content.append({
                        "name": service_model["name"], # display name of the model
                        "file": filename, # filename of the model
                        "hash": service_model["md5sum"], # md5 sum of the model
                        "mem": float(service_model["ramrequired"]), # required memory in gb
                        "type": service_model["type"].lower(),
                        "url": url,
                        "description": html_desc.get_text(' ', strip=True),
                        "prompt_template": service_model["promptTemplate"] or None,
                        "system_prompt": service_model["systemPrompt"] or None
                    })

                fp = open(self.model_path + "/models.json", 'w')
                fp.write(json.dumps(json_content, indent=4, sort_keys=True))
                fp.flush()
                fp.close()


            for model in json_content:
                
                name = model["name"]
                filename = model["file"]
                hash = model["hash"]
                url = model["url"]

                valid = False

                # Check the file hash against what was downloaded
                if self.skip_integrity_check == False:
                    if self._check_hash(filename, hash):
                        logger.info(f"Verified model integrity: {name} ({filename})")
                        valid = True
                    else:
                        logger.warning(f"Model integrity check for: {name} ({filename}) failed. Re-downloading ...")
                else:
                    valid = True

                # Check if the file exists, if not download it
                if not os.path.isfile(f"{self.model_path}/{filename}") or not valid:
                    success = self._download_model(url, filename)
                    if not success:
                        logger.warning(f"Failed to download and save model {name} ({filename}) from {url} !")
                        continue

                    # Verify hash of the downloaded file
                    if self.skip_integrity_check == False:
                        if self._check_hash(filename, hash):
                            valid = True
                    else:
                        valid = True


                # After all validations are complete...
                if valid:
                    self.models.append(model)

            if len(json_content) == 0:
                raise Exception("No models to load!")


            self.gpt_ready = True
            logger.info(f"Successfully verified and loaded {len(self.models)} models")

            for client in self.clients:
                self._send_models(client)

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
