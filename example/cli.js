window.addEventListener("load", function() {

	const MAX_RETRIES = 3; // Infinity
	const SERVER = "ws://localhost:8184";
	const PROMPT = "[[gb;#00FF00;]HUMAN>] ";
	var ws = null;
	var still_down = false;
	var term = null;
	var previous_cursor_pos = null;
	var session = null;

	var query = {
		"question": null,
		"answered": true
	};
	
	const OPTIONS = {
		connectionTimeout: 1000,
		maxRetries: MAX_RETRIES,
		startClosed: false
	};

	term = $('#terminal').terminal(function(command) {
		if (command.trim() !== '') {
			try {
				if (command.startsWith("/")) {
					var cmds = command.split(" ");

					switch(cmds[0]) {
						case "/help":
							this.clientEcho("Commands:");
							this.echo("\t- /help ..................... Shows this command list.");
							this.echo("\t- /reconnect ................ Re-establish WebSocket connection.");
							this.echo("\t- /session <show/destroy> ...  disconnect.");
							break;
							case "/reconnect":
								ws.reconnect();
								break;
						default:
							this.clientEcho("[[;#FF0000;]Invalid command.]");
							break;
					}

				} else {
					query["question"] = command;
					query["answered"] = false;
					ws.send(JSON.stringify({"msg": "chat", "content": {"type": "plain", "prompt": btoa(query["question"])} }));
					this.echo("<i class='fa fa-refresh fa-spin'></i>&nbsp;Awaiting response from server ...", {raw: true, newline: false})
					previous_cursor_pos = this.last_index();
					this.freeze(true);
				}
			} catch(e) {
				this.error(new String(e));
			}
		}
	}, {
		greetings: [
			"gpt4all-service 0.1.0",
			"",
			"Human Interface Service Console (Model: gpt4all GGML 13b nickname 'snoozy')",
			"Type [[;#FFFFFF;]'/help'] for a list of system commands."
		].join("\n"),
		name: 'chat',
		prompt: PROMPT
	});

	term.systemEcho = (msg, opts) => {
		//term.echo(`[[;#FF00FF;]${$.terminal.escape_brackets('[Server]')}] ${msg}`, opts);
		term.echo(`[[;#FFAA22;#000000]${$.terminal.escape_brackets('[SYSTEM]')}] ${msg}`, opts);
	};

	term.clientEcho = (msg, opts) => {
		term.echo(`[[;#00FFFF;#000000]${$.terminal.escape_brackets('[CLIENT]')}] ${msg}`, opts);
	};

	term.freeze(true);
	
	ws = new ReconnectingWebSocket(SERVER, [], OPTIONS);
	
	wslog("Connecting to " + SERVER + " ...");
	term.clientEcho("Connecting to host " + SERVER + " ...")
	
	ws.addEventListener('open', (event) => {
		wslog("Connection established with host");
		if (previous_cursor_pos != null) {
			term.update(previous_cursor_pos, "");
			previous_cursor_pos = null;
		}
		if (session == null) {
			ws.send(JSON.stringify({"msg": "session", "content": {"status": "create"}}));
		} else {
			ws.send(JSON.stringify({"msg": "session", "content": {"status": "resume", "token": session}}));
		}
		term.clientEcho("Status: connected");
		term.freeze(false);
		still_down = false;
	});
	
	ws.addEventListener('close', (event) => {
		if (!still_down) {
			wslog("Disconnected from host");
			// push message down one
			if (previous_cursor_pos != null) {
				term.update(previous_cursor_pos, "");
				previous_cursor_pos = null;
			}
			term.freeze(false);
			term.clientEcho("Status: disconnected");
			term.freeze(true);
			if (query["question"] !== null && !query["answered"]) {
				term.echo("<i class='fa fa-refresh fa-spin'></i>&nbsp;Awaiting response from server ...", {raw: true, newline: false})
				previous_cursor_pos = term.last_index();
				term.freeze(true);
			}
			still_down = true;
		}
	});
	
	ws.addEventListener('message', (event) => {
		var data = JSON.parse(event.data);

		if (data["msg"] === "system") {
			var message = atob(data["content"]["data"]);
			wslog(`[sysmsg] ${message}`);

			// push message down one
			if (previous_cursor_pos != null) {
				term.update(previous_cursor_pos, "");
				previous_cursor_pos = null;
			}
			term.systemEcho(`${message}`);
			if (query["question"] !== null && !query["answered"]) {
				term.echo("<i class='fa fa-refresh fa-spin'></i>&nbsp;Awaiting response from server ...", {raw: true, newline: false})
				previous_cursor_pos = term.last_index();
				term.freeze(true);
			}
		}

		if (data["msg"] === "session") {
			var create = session == null;

			wslog(`[session] ${session == null ? "creation" : "resume"} ${data["success"] ? "successful" : "error"}: ${data["content"]}`);
			
			// Possibly an expired token?
			if (!data["success"]) {
				session = null;
				ws.send(JSON.stringify({"msg": "session", "content": {"status": "create"}}));
				return;
			}

			// Set new token
			session = data["content"];

			// If a previous question was still un-answered, ask it again!
			if (query["question"] !== null && !query["answered"]) {
				ws.send(JSON.stringify({"msg": "chat", "content": {"type": "plain", "prompt": btoa(query["question"])} }));
			}

			if (create) {
				// push message down one
				if (previous_cursor_pos != null) {
					term.update(previous_cursor_pos, "");
					previous_cursor_pos = null;
				}
				term.systemEcho(`New session token issued <${session}>`);
				if (query["question"] !== null && !query["answered"]) {
					term.echo("<i class='fa fa-refresh fa-spin'></i>&nbsp;Awaiting response from server ...", {raw: true, newline: false})
					previous_cursor_pos = term.last_index();
					term.freeze(true);
				}
			}
		}

		if (data["msg"] === "chat") {
			var message = atob(data["content"]);

			query["question"] = null;
			query["answered"] = true;

			if (previous_cursor_pos != null) {
				term.update(previous_cursor_pos, "");
				previous_cursor_pos = null;
			}
			term.echo(message, {typing: true, delay: 30});
			term.freeze(false);
		}

	});
	
	ws.addEventListener('error', (event) => {
		//console.log(event);
	});

});

function wslog(msg, ...obj) {
	console.log("%c[GatewaySocket]%c %s%c", "color:#A199FF;font-weight:bold", null, msg, null, ...obj);
}