# JavaScript Client API and examples

## Simple Example

```js
const sessionSettings = {
	"temperature": 0.8
};

function onOpen() {
	console.log("connection opened");
	client.createSession(sessionSettings);
}

function onClose() {
	console.log("connection closed");
}

/*
function onSessionStatus(state, sessionId, error) {
	if (error) {
		console.log(`session error while trying to ${state}: ${error}`);
		return;
	}
	if (state == "destroy") {
		console.log(`session destroyed`);
		return;
	}

	console.log(`successful '${state}' of session ${sessionId}`);
	client.sendMessage("Hello world!");
}
*/

function onChat(type, sender, message, bot, error) {
	
	if (error) {
		console.error(`chat error: ${error}`);
		return;
	}

	if (type != "text") {
		console.error(`only 'text' type is supported`);
		return;
	}

	console.log(`${sender}: ${message}`);
}

const client = new Gpt4AllBox();

client.addEventListner("connect", onOpen);
client.addEventListner("disconnect", onClose);
//client.addEventListner("session", onSession);
client.addEventListner("chat", onChat);

client.connect("ws://localhost:8184");
client.newSession(sessionSettings, (event) => {
	
	if (!event.success) {
		console.log(`session error while trying to create session: ${error}`);
		return;
	}

	console.log(`session ${sessionId} ${state}ed`);
	client.sendMessage("Hello world!");
});
```



### API

Parameters prefixed with `*` are optional.
Functions prefixed with `*` are planned or in development and may not work or even exist yet.

| Function                             | Returns  | Description                                                           |
|--------------------------------------|----------|-----------------------------------------------------------------------|
| connect(url, *wsParams)              |          | Connect to a WebSocket server, optional web socket params.            |
| disconnect()                         |          | Disconnect from the WebSocket server.                                 |
| isConnected()                        | boolean  | If the client is connected or not.                                    |
| isSessionReady()                     | boolean  | If the client is has a valid session ready to use.                    |
| getSessionId()                       | string   | Get the current sessionId.                                            |
| *getSessionIds()                     | string[] | Get an array of owned sessionId's represented as strings.             |
| addEventListener(event, callback)    |          | Call callback upon an event, see Events table below.                  |
| removeEventListener(event, callback) |          | Remove a listener.                                                    |
| sessionCreate(settings, *callback)   |          | Request a new session with the json settings provided.                |
| sessionResume(sessionId, *callback)  |          | Request a session be resumed by its id.                               |
| sessionDestroy(sessionId, *callback) |          | Request a session be destroyed by its id.                             |
| sessionStatus(sessionId, *callback)  |          | Request a new session with the json settings provided.                |



### Events

| Name            | Callback Parameters                          | Description                                             |
|-----------------|----------------------------------------------|---------------------------------------------------------|
| `connect`       |                                              | Connection has been opened successfully.                |
| `disconnect`    |                                              | Connection is closed.                                   |
| `system`        | type, message                                | System message from the server.                         |
| `session`       | type, error, *sessionId *status, *settings  | Session event.                                          |
| `chat`          | type, sender, message, bot, error            | Chat message event.                                     |
