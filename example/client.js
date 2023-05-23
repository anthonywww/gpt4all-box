'use strict';
// gpt4all-box Client Library Version 1.0.0

(function (global, factory) {
	if (typeof define === 'function' && define.amd) {
		define([], factory);
	} else if (typeof module !== 'undefined' && module.exports){
		module.exports = factory();
	} else {
		global.Gpt4AllBox = factory();
	}
})(this, function () {

	const NAME = "gpt4all-box";
	const SHORT_NAME = "g4ab";
	const VERSION = {major:1, minor:0, patch:0};
	const PING_INTERVAL = 1000;
	const WATCHDOG_INTERVAL = 1000 * 10;

	const Packet = {
		PING: "ping",
		SYSTEM: "system",
		SESSION: "session",
		CHAT: "chat"
	};

	const SessionState = {
		IDLE: "idle",
		PROCESSING: "processing"
	}

	const genRanHex = size => [...Array(size)].map(() => Math.floor(Math.random() * 16).toString(16)).join('');

	class Gpt4AllBox {

		constructor(options) {

			// Default settings
			var settings = {
				/** Whether this instance should log messages. */
				debug: false,

				/** Use the native browser's built-in WebSocket library or a custom one with the same API. */
				websocket: WebSocket
			};

			if (!options) {
				options = {};
			}

			// Overwrite and define settings with options if they exist.
			for (var key in settings) {
				if (typeof(options[key]) !== 'undefined') {
					settings[key] = options[key];
				}
			}

			this._url = null;
			this._settings = settings;
			this._ws = null;
			this._eventListeners = {
				"connect": [],
				"disconnect": [],

				"system": [],
				"session": [],
				"chat": []
			};
			this._sessions = [];
			this._session = null;
			this._lastPingMilliseconds = 0;
			this._cids = [];
		}

		isConnected() {
			if (!this._ws) {
				return false;
			}
			return this._ws.readyState == this._ws.OPEN;
		}

		isSessionReady() {
			if (!this._session) {
				return false;
			}
			return typeof(this._session) == "object";
		}

		getSessionId() {
			if (!this.isSessionReady()) {
				return null;
			}
			return this._session.id;
		}

		getSessionIds() {
			return null;
		}

		/**
		 * Callback on a specific type of event.
		 * 
		 * event = ["open", "close", "system", "session", "chat"]
		 */
		addEventListener(event, callback) {
			if (typeof(callback) !== "function") {
				this._log("error", `callback for event listener "${event}" must be a function`)
				return;
			}
			if (!event in this._eventListeners) {
				this._log("error", `unknown event listener type "${event}"`)
				return;
			}
			if (callback in this._eventListeners[event]) {
				this._log("warn", `callback for event listener "${event}" already exists`)
				return;
			}
			this._eventListeners[event].push(callback);
		}

		removeEventHandler(event, callback) {
			if (typeof(callback) !== "function") {
				this._log("error", `callback for event listener "${event}" must be a function`)
				return;
			}
			if (!event in this._eventListeners) {
				this._log("error", `unknown event listener type "${event}"`)
				return;
			}
			if (!callback in this._eventListeners[event]) {
				this._log("warn", `callback for event listener "${event}" does not exist`)
				return;
			}
			const index = this._eventListeners[event].indexOf(callback);
			if (index > -1) {
				this._eventListeners[event].splice(index, 1);
			}
		}

		connect(url, ...wsParams) {

			if (this.isConnected()) {
				this._log("error", `attempted to connect to "${url}" while already connected to "${this._url}", call disconnect() first.`);
				return;
			}

			this._url = url;
			this._ws = new this._settings.websocket(url, [], ...wsParams);
			this._ws.log = (...x) => console.log("%c[GatewaySocket]%c", "color:#A199FF;font-weight:bold", null, ...x);
			
			this._ws.log(`Connecting to ${this._url} ...`);

			this._ws.addEventListener("open", ((event) => {
				this._ws.log(`Connection established with host ${this._url}`);
				this._pingInterval = setInterval(this._ping.bind(this), PING_INTERVAL);
				this._watchdogInterval = setInterval(this._watchdog.bind(this), WATCHDOG_INTERVAL);
				this._lastPingMilliseconds = 0;
				
				for (var i in this._eventListeners["connect"]) {
					this._eventListeners["connect"][i]();
				}
			}).bind(this));

			this._ws.addEventListener("close", ((event) => {
				this._ws.log(`Lost connection with host ${this._url}`);
				
				clearInterval(this._pingInterval);
				clearInterval(this._watchdogInterval);
	
				this._lastPingMilliseconds = 0;
				this._url = null;
				delete this._ws;

				for (var i in this._eventListeners["disconnect"]) {
					this._eventListeners["disconnect"][i]();
				}
			}).bind(this));

			this._ws.addEventListener("error", ((event) => {
				this._log("error", "websocket error:", event);
			}).bind(this));

			this._ws.addEventListener("message", ((event) => {
				const data = JSON.parse(event.data);

				// Sanity checks
				if (!typeof(data) == "object" || !data.msg || !data.cid) {
					this._log("error", "[network] protocol error: server not responding with a MSG or CID");
					this.disconnect();
					return;
				}
				
				if (!data.msg in Packet) {
					this._log("error", `[network] protocol error: server sending an invalid MSG type: ${data.msg}`);
					this.disconnect();
					return;
				}

				// Call context callbacks
				if (data.cid != null) {
					var consumed = false;
					for (var i in this._cids) {
						const cid = this._cids[i];
						if (data.cid == cid.id) {
							cid.func(data);
							var index = this._cids.indexOf(cid);
							this._cids.splice(index, 1);
							consumed = true;
						}
					}
					if (consumed) {
						this._log("debug", `[network] received message ${data.msg.toUpperCase()} was consumed by cid ${data.cid}`);
						return;
					}
				}

				this._log("debug", `[network] received message ${data.msg.toUpperCase()}`);

				// Packet handling
				if (data.msg == Packet.PING) {
					
				} else if (data.msg == Packet.SESSION) {

				} else if (data.msg == Packet.CHAT) {
					const type = data.content.type;
					const sender = data.content.sender;
					const message = atob(data.content.data);
					const bot = data.content.bot;
					const error = data.content.error;
					for (var i in this._eventListeners["chat"]) {
						this._eventListeners["chat"][i](type, sender, message, bot, error);
					}
				} else if (data.msg == Packet.SYSTEM) {
					const type = data.content.type;
					const message = atob(data.content.data);
					for (var i in this._eventListeners["system"]) {
						this._eventListeners["system"][i](type, message);
					}
				}


			}).bind(this));
		}

		disconnect() {
			if (!this.isConnected()) {
				this._log("error", "attempted to disconnect when not connected")
				return;
			}

			// We might wanna hang on to the session ...
			/*
			if (this._session) {
				this._send(Packet.SESSION, {
					"request": "destroy",
					"session_id": this._session.id
				});
			}
			*/

			this._ws.close();
		}

		getPing() {
			if (!this.isConnected()) {
				return 0;
			}
			return this._lastPingMilliseconds;
		}

		sessionCreate(settings, callback) {
			if (!this.isConnected()) {
				this._log("error", "attempted to create a session when not connected")
				return;
			}
			this._send(Packet.SESSION, {
				"request": "create",
				"settings": settings
			}, ((response) => {
				const msg = response.msg;
				const contextId = response.cid;
				const content = response.content;
				if (content.success) {
					this._session = {
						"id": content["session_id"],
						"created": new Date().getTime() / 1000
					};
					this._sessions.push(this._session);
				}
				for (var i in this._eventListeners["session"]) {
					var type = "create";
					var sessionId = content["session_id"];
					var error = content["error"];
					this._eventListeners["session"][i](type, error, sessionId);
				}
				if (typeof(callback) == "function") {
					callback(content);
				}
			}).bind(this));
		}

		sessionResume(sessionId, callback) {
			if (!this.isConnected()) {
				this._log("error", "attempted to resume a session when not connected")
				return;
			}
			this._send(Packet.SESSION, {
				"request": "resume",
				"session_id": sessionId
			}, ((response) => {
				const msg = response.msg;
				const contextId = response.cid;
				const content = response.content;
				if (content.success) {
					this._session = {
						"id": sessionId,
						"created": new Date().getTime() / 1000
					};
					this._sessions.push(this._session);
				}
				for (var i in this._eventListeners["session"]) {
					var type = "resume";
					var error = content["error"];
					this._eventListeners["session"][i](type, error, sessionId);
				}
				if (typeof(callback) == "function") {
					callback(content);
				}
			}).bind(this));
		}

		sessionDestroy(sessionId, callback) {
			if (!this.isConnected()) {
				this._log("error", "attempted to destroy a session when not connected")
				return;
			}
			this._send(Packet.SESSION, {
				"request": "destroy",
				"session_id": sessionId
			}, ((response) => {
				const msg = response.msg;
				const contextId = response.cid;
				const content = response.content;
				if (content.success) {
					this._session = null;
				}
				for (var i in this._eventListeners["session"]) {
					var type = "destroy";
					var error = content["error"];
					this._eventListeners["session"][i](type, error, sessionId);
				}
				if (typeof(callback) == "function") {
					callback(content);
				}
			}).bind(this));
		}

		sessionStatus(sessionId, callback) {
			if (!this.isConnected()) {
				this._log("error", "attempted to get the status about a session when not connected")
				return;
			}
			this._send(Packet.SESSION, {
				"request": "status",
				"session_id": sessionId
			}, ((response) => {
				const msg = response.msg;
				const contextId = response.cid;
				const content = response.content;
				const type = "status";
				const error = content["error"];
				const status = content["status"];
				const settings = content["settings"];
				for (var i in this._eventListeners["session"]) {
					this._eventListeners["session"][i](type, error, sessionId, status, settings);
				}
				if (typeof(callback) == "function") {
					callback(content);
				}
			}).bind(this));
		}

		sendChat(message) {
			if (!this.isConnected()) {
				this._log("error", "attempted to get the status about a session when not connected")
				return;
			}
			this._send(Packet.CHAT, {
				"type": "text",
				"data": btoa(message)
			}, ((response) => {
				const msg = response.msg;
				const contextId = response.cid;
				const content = response.content;
				const type = "text";
				const sender = content.sender;
				const message = atob(content.data);
				const bot = content.bot;
				const error = content.error;
				for (var i in this._eventListeners["chat"]) {
					this._eventListeners["chat"][i](type, sender, message, bot, error);
				}
				if (typeof(callback) == "function") {
					callback(content);
				}
			}).bind(this));
		}


		_log(level, ...objects) {
			if (!this._settings.debug) {
				return;
			}
			console[level](`[${NAME}]`, ...objects);
		}

		_ping() {
			if (!this.isConnected()) {
				return;
			}
			const start = new Date().getTime();
			this._send(Packet.PING, null, ((response) => {
				if (response.msg !== Packet.PING) {
					this._log("warn", `bad MSG ${response.msg} in response to MSG ${Packet.PING}`)
				}
				const end = new Date().getTime();
				const diff = end - start;
				// This is actually the RTT
				this._lastPingMilliseconds = diff;
				this._log("debug", `[ping] RTT: ${diff}ms CID: ${response.cid}`);
			}).bind(this));
			
		}

		_watchdog() {
			if (!this.isConnected()) {
				return;
			}
			const cids = this._cids.length;
			if (cids > 0) {
				this._log("debug", `unconsumed cids: ${cids}`);
			}
		}

		_send(packet, content, callback, contextId) {

			// Generate a new CID if one is not provided
			contextId = contextId == null ? genRanHex(32) : contextId

			if (typeof(callback) == "function") {
				this._cids.push({
					id: contextId,
					func: callback
				});
			}

			var json = {
				"msg": packet,
				"cid": contextId,
				"content": content
			};

			this._log("debug", `[network] sending ${packet.toUpperCase()} with cid ${contextId}`);
			this._ws.send(JSON.stringify(json));
		}

	}

	// Constants
	Gpt4AllBox.NAME = Object.freeze(NAME);
	Gpt4AllBox.SHORT_NAME = Object.freeze(SHORT_NAME);
	Gpt4AllBox.VERSION = Object.freeze(VERSION);
	Gpt4AllBox.Packet = Object.freeze(Packet);
	Gpt4AllBox.SessionState = Object.freeze(SessionState);
	
	return Gpt4AllBox;
});