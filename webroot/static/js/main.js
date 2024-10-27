// javascript here

Common.init(async () => {
	document.getElementById("eqpls-access-token").innerText = Common.Auth.accessToken;
	Common.WSock.connect(
		"/router/v1/websocket",
		async (socket, data) => {
			console.log(JSON.parse(data), socket);
		},
		async (socket) => {
		}
	);
}).login();