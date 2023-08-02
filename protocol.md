# Protocol datagram specification

All the data over the WebSocket is represented in JSON.

Packet types:

- PING
  - C/S: `ping` - Ping the server.
- SESSION
  - C/S: `status` - Show the current session state relating to this client (if any).
  - C:   `create` - Create a new session.
  - C:   `resume` - Resume an active session by its id (if it has not expired).
  - C/S: `destroy` - Destroy (force expire) an active session.
- CHAT
  - C/S: `text` - Send/receieve a text chat message to or from the chat agent or peer.
- SYSTEM
  - S:   `message` - Show a message from the server.
  - C/S: `models` - Show all available models this server has.
























## PING



### Ping
Simple Ping/Pong

#### Request
```json
{
	"msg": "ping",
	"cid": "1a2b3c4d",
	"content": null
}
```

#### Response
```json
{
	"msg": "ping",
	"cid": "1a2b3c4d",
	"content": null
}
```

































## SESSION




### Session Create Request
In order to do anything the client must first send a session start request.

#### Request
```json
{
	"msg": "session",
	"cid": "1a2b3c4d",
	"content": {
		"request": "create",
		"settings": {
			"model": "ggml-gpt4all-l13b-snoozy.bin",
			"temperature": 0.8,
			"seed": 1234
		}
	}
}
```

#### Response
```json
{
	"msg": "session",
	"cid": "1a2b3c4d",
	"content": {
		"session_id": "111111111",
		"success": true,
		"error": null
	}
}
```







### Session Resume Request
This will resume a session if it exists.

#### Request
```json
{
	"msg": "session",
	"cid": "1a2b3c4d",
	"content": {
		"request": "resume",
		"session_id": "1234abcd"
	}
}
```

#### Response
```json
{
	"msg": "session",
	"cid": "1a2b3c4d",
	"content": {
		"success": true,
		"error": null
	}
}
```






### Session Status Request
This can be sent at any time to show the info about a session.

Response status can be:
- initializing
- idle
- processing

#### Request
```json
{
	"msg": "session",
	"cid": "1a2b3c4d",
	"content": {
		"request": "status",
		"session_id": "1234abcd"
	}
}
```

#### Response
```json
{
	"msg": "session",
	"cid": "1a2b3c4d",
	"content": {
		"success": true,
		"error": null,
		"status": "idle",
		"settings": {
			"model": "ggml-gpt4all-l13b-snoozy.bin",
			"temperature": 0.8,
			"seed": 1234
		}
	}
}
```





### Session Destroy Request
This can only be sent to the session you are currently using.

#### Request
```json
{
	"msg": "session",
	"cid": "1a2b3c4d",
	"content": {
		"request": "destroy",
		"session_id": "1234abcd"
	}
}
```

#### Response
```json
{
	"msg": "session",
	"cid": "1a2b3c4d",
	"content": {
		"success": true,
		"error": null
	}
}
```



































## CHAT



### Chat Message
This is a message from the client to the server.

#### Request
```json
{
	"msg": "chat",
	"cid": "1a2b3c4d",
	"content": {
		"type": "text",
		"session_id": "1234abcd",
		"data": "<base64 encoded message>"
	}
}
```

#### Response
```json
{
	"msg": "chat",
	"cid": "1a2b3c4d",
	"content": {
		"success": true,
		"error": false,
		"session_id": "1234abcd",
		"sender": "Alice",
		"bot": true,
		"type": "text",
		"data": "<base64 encoded message>"
	}
}
```


























## SYSTEM






### Models
Listing of all supported models this system has.

#### Request
```json
{
	"msg": "models",
	"cid": "1a2b3c4d",
	"content": null
}
```

#### Response
```json
{
	"msg": "models",
	"cid": "1a2b3c4d",
	"content": {
		"models": [
			{
				"name": "ggml-gpt4all-l13b-snoozy.bin",
				"description": null
			}
		],
		"success": true,
		"error": null
	}
}
```







### Message
A message from the system (not the agent).

#### Response
```json
{
	"msg": "system",
	"cid": "1a2b3c4d",
	"content": {
		"type": "message",
		"data": "<base64 encoded message>"
	}
}
```