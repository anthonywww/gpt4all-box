#!/usr/bin/env python
# -*- coding: utf-8 -*-
from strenum import StrEnum

class GPTStatus(StrEnum):
    INITIALIZING = "initializing",
    IDLE = "idle",
    PROCESSING = "processing"
