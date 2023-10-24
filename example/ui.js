
const getRanHex = (size) => {
	let result = [];
	let hexRef = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', 'a', 'b', 'c', 'd', 'e', 'f'];
	for (let n = 0; n < size; n++) {
		result.push(hexRef[Math.floor(Math.random() * 16)]);
	}
	return result.join('');
}

const ELEMENTS = {
	"chat": "#chat",
	"logs": "#logs",
	"info_status": "#info-status",
	"system_message": "#system-message",
	"session_model": "#session-model",
	"new_session_button": "#new-session"
};

const WEBSOCKET_PARAMS = {
	connectionTimeout: 3000,
	startClosed: false
}

const SESSION_STATUS = {
	init: "initializing",
	idle: "idle",
	awaiting: "awaiting",
	terminated: "terminated"
}

const COOKIE_NAME = "gpt4ab-state";

var currentTab = null;
var tabs = [];
var logs = [];
var cookieInitialized = null;

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
		return Math.round(elapsed / 1000) + ' seconds ago';
	} else if (elapsed < msPerHour) {
		return Math.round(elapsed / msPerMinute) + ' minutes ago';
	} else if (elapsed < msPerDay) {
		return Math.round(elapsed / msPerHour) + ' hours ago';
	} else if (elapsed < msPerMonth) {
		return 'approximately ' + Math.round(elapsed / msPerDay) + ' days ago';
	} else if (elapsed < msPerYear) {
		return 'approximately ' + Math.round(elapsed / msPerMonth) + ' months ago';
	} else {
		return 'approximately ' + Math.round(elapsed / msPerYear) + ' years ago';
	}
}

function updateTimestamps() {
	$("time.timestamp").each(function () {
		let previous_string = parseInt(($(this).attr("datetime")));
		let previous = new Date(previous_string * 1000);
		let current = new Date();
		let diff = timeDifference(current, previous);
		$(this).attr("title", diff);
	});
}

function getCurrentTab() {
	if (currentTab != null) {
		if (currentTab <= tabs.length) {
			if (tabs[currentTab] != null) {
				return tabs[currentTab];
			}
		}
	}
	return null;
}

function renderChat() {
	if (currentTab == null) {
		console.error("tried to render chat on a null tab!");
		return;
	}

	$(ELEMENTS.chat).children().remove();

	for (var i=0; i<currentTab.chat_log.length; i++) {
		const entry = currentTab.chat_log[i];
		const css_class = entry.css_class;
		const time = entry.time;
		const date_formatted = entry.date_formatted;
		const display_name = entry.display_name;
		const message = entry.message;

		$(ELEMENTS.chat).append(`
			<div class="chat-message ${css_class}">
				<time class="timestamp" datetime="${time}">${date_formatted}</time>
				<span class="sender">${display_name}</span>
				<div class="content">
					${message}
				</div>
			</div>
		`);
	}

	$(ELEMENTS.chat).animate({ scrollTop: $(ELEMENTS.chat).height() }, 1000);
}


function addToChat(tab_id, sender, display_name, is_bot, message) {
	const ampm = true;
	const date = new Date();
	const hour = (date.getHours() < 10 ? "0" + date.getHours() : date.getHours());
	const minute = (date.getMinutes() < 10 ? "0" + date.getMinutes() : date.getMinutes());
	const second = (date.getSeconds() < 10 ? "0" + date.getSeconds() : date.getSeconds());
	const date_formatted = (ampm ? `${hour > 12 ? hour - 11 : hour}:${minute}:${second} ${hour >= 12 ? "PM" : "AM"}` : `${hour}:${minute}:${second}`);
	const unix_time = Math.floor(date.getTime() / 1000);

	var css_class = "";

	if (sender == "system") {
		css_class = "chat-message-system";
	} else if (sender == "client") {
		css_class = "chat-message-client";
	} else if (sender == "user") {
		message = marked.parse(message);
	}
	if (is_bot) {
		css_class = "chat-message-agent";
	}

	var entry = {
		"time": unix_time,
		"date_formatted": date_formatted,
		"sender": sender,
		"display_name": display_name,
		"css_class": css_class,
		"message": message
	};

	// this means broadcast to all tabs
	if (tab_id == null) {

		for (var i=0; i<tabs.length; i++) {
			var tab = tabs[i];
			tab.chat_log.push(entry);
		}

		if (currentTab != null) {
			renderChat();
		}
	} else {
		var tab = null;

		for (var i=0; i<tabs.length; i++) {
			var t = tabs[i];
			if (t.tab_id == tab_id) {
				tab = t;
				break;
			}
		}
	
		if (tab == null) {
			console.error("tab does not exist!");
			return;
		}
		
		tab.chat_log.push(entry);

		if (currentTab != null) {
			renderChat();
		}
	}

	/*
	if (sender == "system") {
		for (var i in tabs) {
			tabs[i].chat_log.push(entry);
		}
	}
	*/

	// Show the changes, if currently on the tab
	/*
	if (getCurrentTab().session_id == sessionId) {
		$(ELEMENTS.chat).append(`
			<div class="chat-message ${css_class}">
				<time class="timestamp" datetime="${unix_time}">${date_formatted}</time>
				<span class="sender">${display_name}</span>
				<div class="content">
					${message}
				</div>
			</div>
		`);

		$(ELEMENTS.chat).animate({ scrollTop: $(ELEMENTS.chat).height() }, 1000);
	}
	*/

}

function updateStats() {

	$("#chat-statusbar-ping").empty();

	if (getCurrentTab() != null) {
		var sess = client.getSessionById(getCurrentTab().session_id);

		if (sess != null) {
			client.sessionStatus(sess.id);
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

	//$("#chat-statusbar-ping").append(`<i class="fa fa-exchange" title="Average RTT ping in milliseconds."></i>&nbsp;${ping}`);
	$("#avg-ping").html(ping);
}

function onConnect() {
	$(ELEMENTS.info_status).text("connected, awaiting models list from server ...");
	$(ELEMENTS.system_message).html(`
		<h5 class="subtitle is-6"><u>SYSTEM MESSAGE</u></h5>
	`);
	$("#server").prop("disabled", true);
	$("#model").prop("disabled", false);
	$("#temperature").prop("disabled", false);

	$("#connect").html("<i class='fa fa-plug'></i>&nbsp;Disonnect");
	$("#connect").addClass("is-danger");
	$("#connect").removeClass("is-success");
	$("#connect").removeClass("is-loading");

	$("#kill").prop("disabled", false);
	$("#send").prop("disabled", false);

	$("#chat-statusbar").addClass("chat-statusbar-normal");
	$("#chat-statusbar-status").html("<i class='fa fa-check'></i>&nbsp;Connected!");
	setTimeout(() => {
		$("#chat-statusbar-status").html("");
	}, 3000);
	
	//$("#chat-statusbar-ping").html(`<i class='fa fa-exchange'></i>&nbsp;${client.getPing()}ms`);

	statsInterval = setInterval(updateStats, 3000);
	
	
	// TODO: restore sessions from cookie?
}

function onDisconnect() {
	$(ELEMENTS.new_session_button).prop("disabled", true);
	$(ELEMENTS.session_model).prop("disabled", true);
	$(ELEMENTS.session_model).children().remove();
	$(ELEMENTS.session_model).append(`
		<option value="" selected>No Models Available</option>
	`);
	$(ELEMENTS.info_status).text("disconnected");
	$(ELEMENTS.system_message).html("");
	$(ELEMENTS.system_message).hide();
	$("#connect").html("<i class='fa fa-plug'></i>&nbsp;Connect");
	$("#connect").addClass("is-success");
	$("#connect").removeClass("is-danger");
	$("#connect").removeClass("is-loading");
	$("#model").prop("disabled", true);
	$("#temperature").prop("disabled", true);

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

function onSystemMessage(type, message) {
	if (type == "message") {
		// FIXME: this should be local per session.
		addToChat(null, "system", `<i class="fa fa-warning" title="This message was sent by the system."></i>&nbsp;SYSTEM`, false, message);

		$(ELEMENTS.system_message).append(`
			<p>${message}</p>
		`);

		$(ELEMENTS.system_message).show();

	} else if (type == "models") {
		// got models from server, unblock spawn session button and populate models

		var models_length = $(ELEMENTS.session_model).children().length;

		if (models_length > 0) {
			$(ELEMENTS.session_model).prop("disabled", false);
			$(ELEMENTS.session_model).children().remove();

			for (var i = 0; i<message.length; i++) {
				var model = message[i];
				var name = model["name"];
				var value = model["file"];
				var description = model["description"];
	
				$(ELEMENTS.session_model).append(`
					<option value="${value}" title="${description}">${name} (${value})</option>
				`);
			}

			models_length = $(ELEMENTS.session_model).children().length;

			$(ELEMENTS.session_model).children().eq(0).prop("selected", true);
			$(ELEMENTS.info_status).text(`connected, loaded ${models_length} models, ready`);
			$(ELEMENTS.new_session_button).prop("disabled", false);
		}

	}
}

function onSessionState(type, error, session_id, status, settings) {

	if (error != null) {
		console.error("session error! ", error);
	}

	if (type == "create") {
		var tab_id = null;
		for (var i=0; i<tabs.length; i++) {
			var tab = tabs[i];
			if (tab.session_id == session_id) {
				tab_id = tab.tab_id;
				break;
			}
		}
		addToChat(tab_id, "client", "Client", false, `<i class="fa fa-info-circle" title="This message is by the client."></i>&nbsp;Session created. (id:<code>${session_id}</code>)`);
	} else if (type == "resume") {
		var tab_id = null;
		for (var i=0; i<tabs.length; i++) {
			var tab = tabs[i];
			if (tab.session_id == session_id) {
				tab_id = tab.tab_id;
				break;
			}
		}

		addToChat(tab_id, "client", "Client", false, `<i class="fa fa-info-circle" title="This message is by the client."></i>&nbsp;Session resumed. (id:<code>${session_id}</code>)`);
	} else if (type == "destroy") {

		
		$("#send").prop("disabled", true);
	} else if (type == "status") {

		if (status == "idle") {
			$("#send").prop("disabled", false);
		} else {
			$("#send").prop("disabled", true);
		}

		if (client.isSessionReady()) {
			for (i in sessions) {
				var sess = sessions[i];
				if (sess.id == client.getSessionId()) {
					sess.status = status;
					break;
				}
			}
		}

	}

}

function onChat(type, session_id, sender, message, bot, error) {

	if (bot == true && awaitingResponse) {
		awaitingResponse = false;
		$("#chat-statusbar-status").html(``);
		$("#chat-statusbar").removeClass("chat-statusbar-awaiting-response");
	}

	const name = (bot ? "<i class='fa fa-desktop' title='This user is a bot.'></i>&nbsp;" + sender : sender);

	// TODO: make this configurable/optional ...
	message = marked.parse(message);

	if (session_id == null) {
		addToChat(null, sender, name, bot, message);
	} else {
		var tab = currentTab;
		
		if (tab != null) {
			for (var t in tabs) {
				if (t.session_id == session_id) {
					tab = t;
					break;
				}
			}
		}

		addToChat(tab.tab_id, sender, name, bot, message);
	}

	if (currentTab != null) {
		renderChat();
	}
}

function updateSessionToCookie() {
	var data = getCookie(COOKIE_NAME);
	if (data == null) {
		setCookie(COOKIE_NAME, {
			"initialized": cookieInitialized || new Date().getTime() / 1000,
			"sessions": sessions
		});
	}
}

function getSessionsFromCookie() {
	var data = getCookie(COOKIE_NAME);
	if (data == null) {
		setSessionToCookie();
	}
	return data["sessions"];
}

function setCookie(name, value, days) {
	var expires = "";
	if (days) {
		var date = new Date();
		date.setTime(date.getTime() + (days * 24 * 60 * 60 * 1000));
		expires = "; expires=" + date.toUTCString();
	}
	document.cookie = name + "=" + (value || "") + expires + "; path=/";
}

function getCookie(name) {
	var nameEQ = name + "=";
	var ca = document.cookie.split(';');
	for (var i = 0; i < ca.length; i++) {
		var c = ca[i];

		while (c.charAt(0) == ' ') {
			c = c.substring(1, c.length);
		}

		if (c.indexOf(nameEQ) == 0) {
			return c.substring(nameEQ.length, c.length);
		}
	}
	return null;
}

function destroyCookie(name) {
	document.cookie = name + '=; Path=/; Expires=Thu, 01 Jan 1970 00:00:01 GMT;';
}

function switchToTab(tab_id) {

	// prevent duplicate action
	if (currentTab == null) {
		if (tab_id == null) {
			return;
		}
	} else {
		if (tab_id == currentTab.tab_id) {
			return;
		}
	}

	$("ul#session-tabs").children().removeClass("is-active");

	// if "info" tab
	if (tab_id == null) {
		currentTab = null;
		$("ul#session-tabs li.is-info-tab").addClass("is-active");
		$("#session-tab").hide();
		$("#info-tab").show();
	} else {
		for (var i=0; i<tabs.length; i++) {
			var tab = tabs[i];
			if (tab.tab_id == tab_id) {
				currentTab = tab;
				break;
			}
		}

		$(`ul#session-tabs li[data-tab-id='${tab_id}']`).addClass("is-active");
		$("#info-tab").hide();
		$("#session-tab").show();
		renderChat();
	}

}





client = new Gpt4AllBox({
	debug: true,
	//websocket: ReconnectingWebSocket
});

client.addEventListener("connect", onConnect);
client.addEventListener("disconnect", onDisconnect);
client.addEventListener("system", onSystemMessage);
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

	$("#show-advanced-toggle").click(() => {
		if ($("#advanced-model-parameters").is(":hidden")) {
			$("#show-advanced-toggle").html(`<i class="fa fa-chevron-up"></i>&nbsp;Hide Advanced Model Parameters`);
			$("#advanced-model-parameters").show();
		} else {
			$("#show-advanced-toggle").html(`<i class="fa fa-chevron-down"></i>&nbsp;Show Advanced Model Parameters`);
			$("#advanced-model-parameters").hide();
		}
	});

	$(ELEMENTS.new_session_button).click(() => {
		//addToChat("client", "Client", false, `<i class="fa fa-info-circle" title="This message was sent by the client."></i>&nbsp;No session found, requesting a new session ...`);
		//addToChat("client", "Client", false, `<i class="fa fa-info-circle" title="This message was sent by the client."></i>&nbsp;Attempting to resume session (id:<code>${sessionId}</code>) ...`);

		var tabId = getRanHex(32);
		var sessionName = $("#session-nickname").val();

		tabs.push({
			"tab_id": tabId,
			"session_id": null,
			"nickname": sessionName,
			"status": SESSION_STATUS.init,
			"status_interval": null,
			"created": Math.floor(new Date().getTime() / 1000),
			"settings": {
				"model": $("#session-model").val(),
				"temperature": parseFloat($("#session-temperature").val()),
				"n_batch": parseInt($("#session-n_batch").val()),
				"top_k": parseInt($("#session-top_k").val()),
				"top_p": parseFloat($("#session-top_p").val()),
				"repeat_penalty": parseFloat($("#session-repeat_penalty").val()),
				"repeat_last_n": parseInt($("#session-repeat_last_n").val()),
				"max_tokens": parseInt($("#session-max_tokens").val()),
			},
			"chat_log": [] 
		});

		//$("ul#session-tabs").children().removeClass("is-active");

		$("ul#session-tabs").append(`
			<li class="is-active" data-tab-id="${tabId}">
				<a class="session-tabs-link">
					<span class="icon is-small">
						<i class="fa fa-comment" aria-hidden="true"></i>
					</span>
					<span>
						${sessionName}
					</span>
				</a>
			</li>
		`);

		$(`ul#session-tabs li[data-tab-id='${tabId}']`).click(() => {
			switchToTab(tabId);
		});

		switchToTab(tabId);

		$("#session-nickname").val("Chat #" + (tabs.length + 1))

		var tab = tabs[tabs.length-1];

		client.sessionCreate(tab.settings, (content) => {

			console.log("c::: " + content);
			tab.session_id = content.session_id;
		});

		addToChat(tab.tab_id, "client", "Client", false, `<i class="fa fa-info-circle" title="This message is by the client."></i>&nbsp;No session found, requesting a new session ...`);


		/*
		// Deal with sessions
		if (sessions.length == 0) {
			// Create a new session
			
			addToChat("client", "Client", false, `<i class="fa fa-info-circle" title="This message was sent by the client."></i>&nbsp;No session found, requesting a new session ...`);
			
			var session_settings = {
				"model": $("#model").val(),
				"temperature": $("#temperature").val()
			};

			client.sessionCreate(session_settings);
		} else {
			// Resume a session
			//client.sessionResume(sessionId);
		}
		*/
	});

	$("ul#session-tabs li").click(() => {
		switchToTab(null);
	});

	$("#send").click(() => {
		// FIXME: client.isSessionReady no longer exists.
		if (client.isConnected()) {

			if (currentTab.session_id == null) {
				console.error("no session id for chat!");
				return;
			}

			var msg = $("#prompt").val();
			$("#prompt").val("");

			addToChat(currentTab.tab_id, "user", "You", false, msg);
			client.sendChat(currentTab.session_id, msg);

			$("#chat-statusbar-status").html(`<i class="fa fa-cog fa-spin fa-fw"></i>Awaiting response from agent ...`);
			$("#chat-statusbar").addClass("chat-statusbar-awaiting-response");
			awaitingResponse = true;
		}
	});

	$("#prompt").keypress((event) => {
		if (event.keyCode == 13 && !event.shiftKey) {
			if (!($("#send").prop("disabled"))) {
				$("#send").click();
			}
			event.preventDefault();
			return false;
		}
	});

	$("#save-as-plain").click(() => {
		var sess_id = currentTab.session_id;

		if (sess_id == null || currentTab.status == SESSION_STATUS.init) {
			alert("Nothing to save because the session was not initialized yet!")
			return;
		}

		var session = client.getSessionId(sess_id);
		var chatLog = currentTab.chat_log;
		
		if (chatLog == null) {
			console.error("Error while trying to export chat as CSV; unknown session id!");
			return;
		}
		var chatStartDate = getHumanDateFormat(new Date(currentTab.created * 1000));
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
		var filename = `chat-log-${Math.floor(date.getTime() / 1000)}.txt`;
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
		var sess_id = currentTab.session_id;

		if (sess_id == null || currentTab.status == SESSION_STATUS.init) {
			alert("Nothing to save because the session was not initialized yet!")
			return;
		}

		var session = client.getSessionId(sess_id);
		var chatLog = currentTab.chat_log;

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
		var filename = `chat-log-${Math.floor(date.getTime() / 1000)}.csv`;
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
		var sess_id = currentTab.session_id;

		if (sess_id == null || currentTab.status == SESSION_STATUS.init) {
			alert("Nothing to save because the session was not initialized yet!")
			return;
		}

		var session = client.getSessionId(sess_id);
		var chatLog = currentTab.chat_log;

		if (chatLog == null) {
			console.error("Error while trying to export chat as CSV; unknown session id!");
			return;
		}
		var data = JSON.stringify(chatLog);
		var a = document.createElement('a');
		var date = new Date();
		var filename = `chat-log-${Math.floor(date.getTime() / 1000)}.json`;
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
