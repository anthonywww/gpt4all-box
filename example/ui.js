
const ELEMENT = {
	"chat": "#chat"
};

const SESSION_SETTINGS = {
	"model": "ggml-gpt4all-l13b-snoozy.bin", // most stable
	//"model": "ggml-gpt4all-j-v1.3-groovy.bin", // weird behavior, random text response
	//"model": "ggml-mpt-7b-chat.bin",
	"temperature": 0.8
}

const WEBSOCKET_PARAMS = {
	connectionTimeout: 3000,
	startClosed: false
}

var sessions = [];
var statsInterval = null;
var awaitingResponse = false;

// Note: The chat log is from a trusted source (i.e. the user and the gpt4all-box server, which the client.js scrubs anyway)
function stripHtml(html) {
	var tmp = document.createElement("div");
	tmp.innerHTML = html;
	var text = tmp.textContent || tmp.innerText || "";
	tmp.remove();
	return text;
}

function getHumanDateFormat(date) {
	var year = date.getFullYear();
	var month = date.getMonth();
	var day = date.getDate();
	var hour = date.getHours();
	var minute = date.getMinutes();
	var second = date.getSeconds();
	if (month < 10) {
		month = "0" + month;
	}
	if (day < 10) {
		day = "0" + day;
	}
	if (hour < 10) {
		hour = "0" + hour;
	}
	if (minute < 10) {
		minute = "0" + minute;
	}
	if (second < 10) {
		second = "0" + second;
	}
	return `${year}-${month}-${day} ${hour}:${minute}:${second}`;
}

function getLocalTimezoneName() {
	const today = new Date();
	const short = today.toLocaleDateString(undefined);
	const full = today.toLocaleDateString(undefined, { timeZoneName: 'long' });

	// Trying to remove date from the string in a locale-agnostic way
	const shortIndex = full.indexOf(short);
	if (shortIndex >= 0) {
		const trimmed = full.substring(0, shortIndex) + full.substring(shortIndex + short.length);

		// by this time `trimmed` should be the timezone's name with some punctuation -
		// trim it from both sides
		return trimmed.replace(/^[\s,.\-:;]+|[\s,.\-:;]+$/g, '');

	} else {
		// in some magic case when short representation of date is not present in the long one, just return the long one as a fallback, since it should contain the timezone's name
		return full;
	}
}

function getLocalTimezoneLocation() {
	return Intl.DateTimeFormat().resolvedOptions().timeZone;
}

function getLocalTimezoneOffset() {
	var date = new Date().getTimezoneOffset() / 60;
	return (date >= 0 ? `+${date}` : `-${date}`);
}

function timeDifference(current, previous) {
	var msPerMinute = 60 * 1000;
	var msPerHour = msPerMinute * 60;
	var msPerDay = msPerHour * 24;
	var msPerMonth = msPerDay * 30;
	var msPerYear = msPerDay * 365;

	var elapsed = current - previous;

	if (elapsed < msPerMinute) {
		return Math.round(elapsed/1000) + ' seconds ago';
	} else if (elapsed < msPerHour) {
		return Math.round(elapsed/msPerMinute) + ' minutes ago';
	} else if (elapsed < msPerDay ) {
		return Math.round(elapsed/msPerHour ) + ' hours ago';
	} else if (elapsed < msPerMonth) {
		return 'approximately ' + Math.round(elapsed/msPerDay) + ' days ago';
	} else if (elapsed < msPerYear) {
		return 'approximately ' + Math.round(elapsed/msPerMonth) + ' months ago';
	} else {
		return 'approximately ' + Math.round(elapsed/msPerYear ) + ' years ago';
	}
}

function updateTimestamps() {
	$("time.timestamp").each(function() {
		let previous_string = parseInt(($(this).attr("datetime")));
		let previous = new Date(previous_string * 1000);
		let current = new Date();
		let diff = timeDifference(current, previous);
		$(this).attr("title", diff);
	});
}

function addToChat(sender, display_name, isBot, message) {
	const ampm = true;
	const date = new Date();
	const hour = (date.getHours() < 10 ? "0" + date.getHours() : date.getHours());
	const minute = (date.getMinutes() < 10 ? "0" + date.getMinutes() : date.getMinutes());
	const second = (date.getSeconds() < 10 ? "0" + date.getSeconds() : date.getSeconds());
	const dateFormatted = (ampm ? `${hour > 12 ? hour - 11 : hour}:${minute}:${second} ${hour >= 12 ? "PM" : "AM"}` : `${hour}:${minute}:${second}`);
	const unixTime = Math.floor(date.getTime() / 1000);
	var css_class = "";
	
	if (sender == "system") {
		css_class = "chat-message-system";
	} else if (sender == "client") {
		css_class = "chat-message-client";
	} else if (sender == "user") {
		message = marked.parse(message);
	}
	if (isBot) {
		css_class = "chat-message-agent";
	}
	$(ELEMENT.chat).append(`
	<div class="chat-message ${css_class}">
		<time class="timestamp" datetime="${unixTime}">${dateFormatted}</time>
		<span class="sender">${display_name}</span>
		<div class="content">
			${message}
		</div>
	</div>
	`);

	$(ELEMENT.chat).animate({scrollTop: $(ELEMENT.chat).height()}, 1000);

	// Now add it to the current sessions' chat log

	if (client.isSessionReady()) {
		var entry = {
			"time": unixTime,
			"sender": sender,
			"is_bot": isBot,
			"message": message
		};
		var chat_log = null;
		for (i in sessions) {
			if (sessions[i].session.id == client.getSessionId()) {
				chat_log = sessions[i].chat_log;
				break;
			}
		}
		if (chat_log != null) {
			chat_log.push(entry);
		}
	}
}

function updateStats() {

	$("#chat-statusbar-ping").empty();

	if (client.isSessionReady()) {
		var sess = null;

		for (i in sessions) {
			if (sessions[i].session.id == client.getSessionId()) {
				sess = sessions[i].session;
				break;
			}
		}

		if (sess != null) {
			client.sessionStatus(sess.id);

			// TODO: make this only show once...
			/*
			if (sess.status == "initializing") {
				$("#chat-statusbar-status").html(`<i class="fa fa-refresh fa-spin"></i>&nbsp;Downloading and initializing agent model for first time use ...`);
			}
			*/

			$("#chat-statusbar-ping").append(`
				<i class="fa fa-cloud" title="Session ID and model agent status."></i>&nbsp;${sess.id.substr(0, 6)}
				[${sess.status}]
				&nbsp;
			`);
		}
	}
	
	var ping = client.getPing();

	if (ping > 500) {
		ping = `<span style="color:#FF0000;">${ping}ms</span>`;
	} else {
		ping = `${ping}ms`;
	}
	
	$("#chat-statusbar-ping").append(`<i class="fa fa-exchange" title="Average RTT ping in milliseconds."></i>&nbsp;${ping}`);
}

function onConnect() {
	$("#server").prop("disabled", true);
	//$("#model").prop("disabled", true);
	//$("#temperature").prop("disabled", true);

	$("#connect").html("<i class='fa fa-plug'></i>&nbsp;Disonnect");
	$("#connect").addClass("is-danger");
	$("#connect").removeClass("is-success");
	$("#connect").removeClass("is-loading");
	
	$("#chat-statusbar").addClass("chat-statusbar-normal");
	$("#chat-statusbar-status").html("<i class='fa fa-check'></i>&nbsp;Connected!");
	setTimeout(() => {
		$("#chat-statusbar-status").html("");
	}, 3000);
	$("#chat-statusbar-ping").html(`<i class='fa fa-exchange'></i>&nbsp;${client.getPing()}ms`);

	statsInterval = setInterval(updateStats, 3000);
	// TODO: restore sessions from cookie?


	// Deal with sessions
	if (sessions.length == 0) {
		// Create a new session
		addToChat("client", "Client", false, `<i class="fa fa-info-circle" title="This message was sent by the client."></i>&nbsp;No session found, requesting a new session ...`);
		client.sessionCreate(SESSION_SETTINGS);
	} else {
		// Resume a session
		var sessionId = sessions[0].session.id;
		addToChat("client", "Client", false, `<i class="fa fa-info-circle" title="This message was sent by the client."></i>&nbsp;Attempting to resume session (id:<code>${sessionId}</code>) ...`);
		client.sessionResume(sessionId);
	}

}

function onDisconnect() {
	$("#connect").html("<i class='fa fa-plug'></i>&nbsp;Connect");
	$("#connect").addClass("is-success");
	$("#connect").removeClass("is-danger");
	$("#connect").removeClass("is-loading");

	$("#connect").html("<i class='fa fa-plug'></i>&nbsp;Connect");
	$("#server").prop("disabled", false);
	$("#kill").prop("disabled", true);
	$("#send").prop("disabled", true);

	$("#chat-statusbar").removeClass("chat-statusbar-normal");
	$("#chat-statusbar-status").html("");
	$("#chat-statusbar-ping").html("");

	if (statsInterval != null) {
		clearInterval(statsInterval);
	}
}

function onSysemMessage(type, message) {
	addToChat("system", `<i class="fa fa-warning" title="This message was sent by the system."></i>&nbsp;SYSTEM`, false, message);
}

function onSessionState(type, error, sessionId, status, settings) {

	if (error != null) {
		console.error("session error! ", error);
	}

	if (type == "create") {
		const sess = {
			"session": {
				"id": sessionId,
				"status": "initializing",
				"created": Math.floor(new Date().getTime() / 1000),
				"settings": {}
			},
			"chat_log": []
		};
		sessions.push(sess);
		//$("#kill").prop("disabled", false);
		addToChat("client", "Client", false, `<i class="fa fa-info-circle" title="This message was sent by the client."></i>&nbsp;Session created. (id:<code>${sessionId}</code>)`);
	} else if (type == "resume") {
		//$("#kill").prop("disabled", false);
		addToChat("client", "Client", false, `<i class="fa fa-info-circle" title="This message was sent by the client."></i>&nbsp;Session resumed. (id:<code>${client.getSessionId()}</code>)`);
	} else if (type == "destroy") {
		$("#kill").prop("disabled", true);
		$("#send").prop("disabled", true);
	} else if (type == "status") {
		
		if (status == "idle") {
			$("#send").prop("disabled", false);
		} else {
			$("#send").prop("disabled", true);
		}

		if (client.isSessionReady()) {
			for (i in sessions) {
				if (sessions[i].session.id == client.getSessionId()) {
					var sess = sessions[i].session;
					sess.status = status;
					break;
				}
			}
		}

	}

}

function onChat(type, sender, message, bot, error) {

	if (bot == true && awaitingResponse) {
		awaitingResponse = false;
		$("#chat-statusbar-status").html(``);
		$("#chat-statusbar").removeClass("chat-statusbar-awaiting-response");
	}

	const name = (bot ? "<i class='fa fa-desktop' title='This user is a bot.'></i>&nbsp;" + sender : sender);

	// TODO: make this configurable/optional ...
	message = marked.parse(message);


	addToChat(sender, name, bot, message);
}

client = new Gpt4AllBox({
	debug: true,
	//websocket: ReconnectingWebSocket
});

client.addEventListener("connect", onConnect);
client.addEventListener("disconnect", onDisconnect);
client.addEventListener("system", onSysemMessage);
client.addEventListener("session", onSessionState);
client.addEventListener("chat", onChat);

// On DOM loaded
window.addEventListener("load", () => {
	bulmaSlider.attach();
	$("#chat").empty();
	$("#chat-statusbar-status").html("");
	$("#chat-statusbar-ping").html("");
	//$("#chat-statusbar").addClass("chat-statusbar-normal");

	///////////////////////////////////////
	// jQuery
	///////////////////////////////////////

	$("#connect").click(() => {
		$("#connect").addClass("is-loading");
		if (client.isConnected()) {
			client.disconnect();
		} else {
			// Client is not connected
			client.connect($("#server").val(), WEBSOCKET_PARAMS);
		}
	});

	$("#send").click(() => {
		if (client.isConnected() && client.isSessionReady()) {
			var msg = $("#prompt").val();
			$("#prompt").val("");
			
			addToChat("user", "You", false, msg);
			client.sendChat(msg);

			$("#chat-statusbar-status").html(`<i class="fa fa-cog fa-spin fa-fw"></i>Awaiting response from agent ...`);
			$("#chat-statusbar").addClass("chat-statusbar-awaiting-response");
			awaitingResponse = true;
		}
	});

	$("#prompt").keypress((event) => {
		if (event.keyCode == 13 && !event.shiftKey) {
			if (!($("#send").prop("disabled")) && !awaitingResponse) {
				$("#send").click();
			}
			event.preventDefault();
			return false;
		}
	});

	$("#save-as-plain").click(() => {
		var chatLog = null;
		for (i in sessions) {
			if (sessions[i].session.id == client.getSessionId()) {
				chatLog = sessions[i].chat_log;
			}
		}
		if (chatLog == null) {
			console.error("Error while trying to export chat as CSV; unknown session id!");
			return;
		}
		var chatStartDate = getHumanDateFormat(new Date(chatLog[0].time * 1000));
		var data = `Chat session started on ${chatStartDate} UTC${getLocalTimezoneOffset()} (${getLocalTimezoneName()})\n\n\n`;
		for (i in chatLog) {
			if (chatLog[i].sender == "client") {
				continue;
			}
			var timestamp = getHumanDateFormat(new Date(chatLog[i].time * 1000));
			var bot = chatLog[i].is_bot;
			var sender = chatLog[i].sender + (bot ? "*" : "");
			var message = stripHtml(chatLog[i].message.trim().replaceAll("\n", " "));
			data += `[${timestamp}] ${sender}: ${message}\n`;
		}

		var a = document.createElement('a');
		var date = new Date();
		var filename = `chat-log-${Math.floor(date.getTime()/1000)}.txt`;
		var blob = new Blob([data], { type: 'text/plain' });
		a.download = filename;
		a.href = window.URL.createObjectURL(blob);
		a.textContent = "";
		a.style = "display:none";
		a.click();
		a.remove();
		delete blob;
	});

	$("#save-as-csv").click(() => {
		var chatLog = null;
		for (i in sessions) {
			if (sessions[i].session.id == client.getSessionId()) {
				chatLog = sessions[i].chat_log;
			}
		}
		if (chatLog == null) {
			console.error("Error while trying to export chat as CSV; unknown session id!");
			return;
		}
		var headers = ["Timestamp", "Sender", "Message"];
		var data = headers.join(",") + "\n";

		for (i in chatLog) {
			if (chatLog[i].sender == "client") {
				continue;
			}
			var timestamp = getHumanDateFormat(new Date(chatLog[i].time * 1000));
			var bot = chatLog[i].is_bot;
			var sender = chatLog[i].sender + (bot ? "*" : "");
			var message = stripHtml(chatLog[i].message.trim().replaceAll("\n", " ")).replaceAll("\"", "\"\"");
			data += `${timestamp},${sender},"${message}"\n`;
		}

		var a = document.createElement('a');
		var date = new Date();
		var filename = `chat-log-${Math.floor(date.getTime()/1000)}.csv`;
		var blob = new Blob([data], { type: 'text/csv' });
		a.download = filename;
		a.href = window.URL.createObjectURL(blob);
		a.textContent = "";
		a.style = "display:none";
		a.click();
		a.remove();
		delete blob;
	});

	$("#save-as-json").click(() => {
		var chatLog = null;
		for (i in sessions) {
			if (sessions[i].session.id == client.getSessionId()) {
				chatLog = sessions[i].chat_log;
			}
		}
		if (chatLog == null) {
			console.error("Error while trying to export chat as CSV; unknown session id!");
			return;
		}
		var data = JSON.stringify(chatLog);
		var a = document.createElement('a');
		var date = new Date();
		var filename = `chat-log-${Math.floor(date.getTime()/1000)}.json`;
		var blob = new Blob([data], { type: 'application/json' });
		a.download = filename;
		a.href = window.URL.createObjectURL(blob);
		a.textContent = "";
		a.style = "display:none";
		a.click();
		a.remove();
		delete blob;
	});


	setInterval(updateTimestamps, 1000);
});
