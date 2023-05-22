#!/usr/bin/env python
# -*- coding: utf-8 -*-
from strenum import StrEnum

class Packet(StrEnum):
    PING = "ping",
    SYSTEM = "system",
    SESSION = "session",
    CHAT = "chat"
