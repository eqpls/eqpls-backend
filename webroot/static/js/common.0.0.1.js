window.Common = window.Common || {
	init: (main) => {
		console.log("(Common) start");

		// Common definitions /////////////////////////////
		Common.main = main;
		Common.url = `https://${Config.endpoint}`;
		Common.Util = Common.Util || {};
		Common.DB = Common.DB || {};
		Common.DB._index = Config.index;
		Common.DB._index.Blob = ["index"];
		Common.Session = Common.Session || { Query: {}, Hash: {}, Cookie: {} };
		Common.Rest = Common.Rest || {};
		Common.WSock = Common.WSock || {};
		Common.Auth = Common.Auth || {};
		Common.Auth.url = `${Common.url}/auth`;
		Common.Account = Common.Account || {};
		Common.Account.url = `${Common.url}/account/v${Config.version}`;
		Common.Uerp = Common.Uerp || {};
		Common.Uerp.url = `${Common.url}/uerp/v${Config.version}`;

		// login service provider handlers ////////////////
		Common.loginServiceProviders = Common.loginServiceProviders || async function() { };
		Common.logoutServiceProviders = Common.logoutServiceProviders || async function() { };

		// Common.Util /////////////////////////////
		Common.Util.utoa = (str) => { return window.btoa(unescape(encodeURIComponent(str))); };
		Common.Util.atou = (str) => { return decodeURIComponent(escape(window.atob(str))); };

		Common.Util._regex_uuid = /^[a-z,0-9,-]{36,36}$/;
		Common.Util.checkUUID = (uuid) => { Common.Util._regex_uuid.test(uuid); };
		Common.Util.getUUID = () => { return crypto.randomUUID(); };

		Common.Util.getRandomString = (length) => {
			let result = "";
			let characters = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
			for (let i = 0; i < length; i++) { result += characters.charAt(Math.floor(Math.random() * 62)); }
			return result;
		};

		Common.Util.setArrayFunctions = (arr) => {
			arr.len = () => { return arr.length; };
			arr.empty = () => {
				if (arr.len() == 0) { return true; }
				else { return false; }
			};
			arr.findById = (id) => {
				arr.forEach((content) => { if (id == content.id) { return content; } });
				return None
			};
			arr.searchByName = (name) => {
				let result = [];
				arr.forEach((content) => { if (content.name.indexOf(name) > -1) { result.push(content); } });
				return setArrayFunctions(result);
			};
			arr.searchByField = (field, value) => {
				let result = [];
				arr.forEach((content) => { if (value == content[field]) { result.push(content); } });
				return setArrayFunctions(result);
			};
			arr.sortAscBy = (field) => {
				if (!arr.empty()) {
					let val = arr[0][field]
					if (typeof val == "string") {
						arr.sort((a, b) => {
							let aval = a[field];
							let bval = b[field];
							return aval < bval ? -1 : aval > bval ? 1 : 0;
						});
					} else if (typeof val == "number") {
						arr.sort((a, b) => { return a[field] - b[field]; });
					} else {
						console.error("could not sort", arr);
					}
				}
				return arr;
			};
			arr.sortDescBy = (field) => {
				if (!arr.empty()) {
					let val = arr[0][field]
					if (typeof val == "string") {
						arr.sort((a, b) => {
							let aval = a[field];
							let bval = b[field];
							return aval > bval ? -1 : aval < bval ? 1 : 0;
						});
					} else if (typeof val == "number") {
						arr.sort((a, b) => { return b[field] - a[field]; });
					} else {
						console.error("could not sort", arr);
					}
				}
				return arr
			};
			arr.print = () => {
				if (arr.empty()) { console.log("this is empty array"); }
				else { console.log(arr); }
			};
			return arr;
		};

		// Common.DB ///////////////////////////////
		function Database(name, tables) {
			this._name = name;
			this._tables = [];
			let request = window.indexedDB.open(this._name, 1);
			request.onsuccess = () => {
				this._conn = request.result;
				tables.forEach((table) => { this[table] = new Table(table, this); });
				Common.DB[name] = this;
			};
			request.onupgradeneeded = () => {
				tables.forEach((table) => { request.result.createObjectStore(table, { keyPath: "id" }); });
				Common.DB[name] = this;
			};
			request.onerror = () => {
				console.error("could not create database");
				Common.DB.pop(name);
			};
		};

		function Table(name, db) {
			this._name = name;
			this._db = db;
			this.readAll = () => {
				return new Promise((resultHandler) => {
					let request = this._db._conn.transaction(this._name).objectStore(this._name).getAll();
					request.onsuccess = () => { resultHandler(Common.Util.setArrayFunctions(request.result)); };
					request.onerror = () => { resultHandler(request); };
				});
			};
			this.read = (id) => {
				return new Promise((resultHandler) => {
					let request = this._db._conn.transaction(this._name).objectStore(this._name).get(id);
					request.onsuccess = () => { resultHandler(request.result); };
					request.onerror = () => { resultHandler(request); };
				});
			};
			this.write = (id, data) => {
				return new Promise((resultHandler) => {
					data.id = id;
					let request = this._db._conn.transaction([this._name], "readwrite").objectStore(this._name).put(data);
					request.onsuccess = () => { resultHandler(data); };
					request.onerror = () => { resultHandler(request); };
				});
			};
			this.delete = (id) => {
				return new Promise((resultHandler) => {
					let request = this._db._conn.transaction([this._name], "readwrite").objectStore(this._name).delete(id);
					request.onsuccess = () => { resultHandler(id); };
					request.onerror = () => { resultHandler(request); };
				});
			};
			this._db._tables.push(name);
			console.log(`(DB.${this._db._name}.${name}) table is created`);
		};

		// Common.Session //////////////////////////
		Common.Session.Query.parse = (query) => {
			let map = {};
			query.replace("?", "").split("&").forEach((q) => {
				if (q) {
					let kv = q.split("=");
					map[kv[0]] = kv[1];
				}
			});
			return map;
		};
		Common.Session.Query.get = () => {
			return Common.Query.parse(window.location.search);
		};

		Common.Session.Hash.parse = (hash) => {
			let map = {};
			hash.replace("#", "").split("&").forEach((h) => {
				if (h) {
					let kv = h.split("=");
					map[kv[0]] = kv[1];
				}
			});
			return map;
		};
		Common.Session.Hash.get = () => {
			return Common.Session.Hash.parse(window.location.hash);
		};

		Common.Session.Cookie.get = (name) => {
			let value = document.cookie.match('(^|;) ?' + name + '=([^;]*)(;|$)');
			return value ? value[2] : null;
		};

		Common.Session.Cookie.set = (name, value, expire, path) => {
			if (!expire) { expire = 3600; }
			if (!path) { path = "/"; }
			var date = new Date();
			date.setTime(date.getTime() + expire * 1000);
			document.cookie = `${name}=${value};expires=${date.toUTCString()};path=${path}`;
		};

		Common.Session.Cookie.del = (name, path) => {
			if (!path) { path = "/"; }
			document.cookie = `${name}=;expires=Thu, 01 Jan 1999 00:00:10 UTC;path=${path}`;
		};

		// Common.Rest /////////////////////////////
		Common.Rest.get = async (url) => {
			return fetch(url, {
				headers: Common.Auth.headers
			}).then((res) => {
				if (res.ok) { return res.json(); }
				throw res
			});
		};

		Common.Rest.post = async (url, data) => {
			return fetch(url, {
				method: "POST",
				headers: Common.Auth.headers,
				body: JSON.stringify(data)
			}).then((res) => {
				if (res.ok) { return res.json(); }
				throw res
			});
		};

		Common.Rest.put = async (url, data) => {
			return fetch(url, {
				method: "PUT",
				headers: Common.Auth.headers,
				body: JSON.stringify(data)
			}).then((res) => {
				if (res.ok) { return res.json(); }
				throw res
			});
		};

		Common.Rest.patch = async (url, data) => {
			return fetch(url, {
				method: "PATCH",
				headers: Common.Auth.headers,
				body: JSON.stringify(data)
			}).then((res) => {
				if (res.ok) { return res.json(); }
				throw res
			});
		};

		Common.Rest.delete = async (url, data) => {
			return fetch(url, {
				method: "DELETE",
				headers: Common.Auth.headers,
				body: data ? data : null
			}).then((res) => {
				if (res.ok) { return res.json(); }
				throw res
			});
		};

		// Common.WSock ////////////////////////////
		Common.WSock.connect = (url, receiver, initiator, closer) => {
			try {
				let socket = new WebSocket(`wss://${Config.endpoint}${url}`);
				socket.sendJson = async (data) => { return socket.send(JSON.stringify(data)); };
				socket.sendData = async (key, value) => { return socket.send(JSON.stringify([key, value])); };
				socket.onmessage = (event) => { receiver(event.target, event.data); };
				socket.onerror = (event) => { console.error("(wsock) error", event); };
				socket.onopen = (event) => {
					console.log("(wsock) open");
					event.target.sendData("auth", Common.Auth.accessToken);
					if (initiator) { initiator(event.target); }
				};
				socket.onclose = (event) => {
					console.log("(wsock) close");
					setTimeout(() => { Common.WSock.connect(url, receiver, initiator, closer); }, 2000);
					if (closer) { closer(event); }
				};
				return socket;
			} catch (e) {
				setTimeout(() => { Common.WSock.connect(url, receiver, initiator, closer); }, 2000);
			}
		};

		// Common.Auth /////////////////////////////
		Common.login = (redirectUri) => {
			let keycloak = new Keycloak({
				url: Common.Auth.url,
				realm: Config.tenant,
				clientId: Config.client
			});
			keycloak.onAuthSuccess = () => {
				Common.Auth.keycloak = keycloak;
				Common.Auth.postLogin = () => {
					Common.Auth.accessToken = Common.Auth.keycloak.token;
					Common.Auth.refreshToken = Common.Auth.keycloak.refreshToken;
					Common.Auth.idToken = Common.Auth.keycloak.idToken;
					Common.Auth.bearerToken = `Bearer ${Common.Auth.accessToken}`
					Common.Auth.headers = {
						"Authorization": Common.Auth.bearerToken,
						"Content-Type": "application/json; charset=utf-8",
						"Accept": "application/json; charset=utf-8"
					};
					return Common.loginServiceProviders().then(Common.Account.getUserInfo().then());
				};
				Common.Auth.postLogin().then(() => {
					if (window.Module) { for (let key in window.Module) { if (window.Module[key].isAutoLogin) { window.Module[key].login(); } }; }
					Common.Auth.startTokenDaemon();
					let databaseNames = Object.keys(Common.DB._index);
					databaseNames.forEach((name) => { new Database(name, Common.DB._index[name]); });
					function waitStableForMain() {
						try {
							for (let i = 0; i < databaseNames.length; i++) {
								let name = databaseNames[i];
								let innerList = Common.DB[name]._tables.sort().join(',');
								let outerList = Common.DB._index[name].sort().join(',');
								if (innerList != outerList) { return setTimeout(checkDB, 200); }
							}
						} catch (e) { return setTimeout(waitStableForMain, 200); }
						if (Common.main) { Common.main(); }
					};
					waitStableForMain();
				});
			};
			keycloak.onAuthError = () => {
				console.error("could not get authorization");
				window.location.replace(redirectUri ? redirectUri : "/");
			};
			keycloak.init({
				onLoad: "login-required",
				redirectUri: redirectUri ? redirectUri : "/"
			});
		};

		Common.logout = (redirectUri) => {
			Common.logoutServiceProviders().then(() => {
				Common.Auth.keycloak.logout({
					redirectUri: redirectUri ? redirectUri : "/"
				}).catch((error) => {
					console.error(error);
					window.location.replace("/");
				});
			}).catch((error) => {
				console.error(error);
			});
		};

		Common.Auth.startTokenDaemon = () => {
			Common.Auth.keycloak.updateToken(300).then((refreshed) => {
				if (refreshed) { Common.Auth.postLogin(); }
				setTimeout(Common.Auth.startTokenDaemon, 60000);
			});
		};

		// Common.Account //////////////////////////
		Common.Account.login = async (username, password) => {
			let tokens = await Common.Rest.post(`${Common.Account.url}/login`, {
				username: username,
				password: password
			});
			Common.Auth.accessToken = tokens.access_token;
			Common.Auth.refreshToken = tokens.refresh_token;
			Common.Auth.bearerToken = `Bearer ${Common.Auth.accessToken}`
			Common.Auth.headers = {
				"Authorization": Common.Auth.bearerToken,
				"Content-Type": "application/json; charset=utf-8",
				"Accept": "application/json; charset=utf-8"
			};
			if (Common.main) { Common.main(); }
		};

		Common.Account.logout = async () => {
			await Common.Rest.get(`${Common.Account.url}/logout?refreshToken=${Common.Auth.refreshToken}`);
			Common.Auth.accessToken = null;
			Common.Auth.refreshToken = null;
			Common.Auth.bearerToken = null;
			Common.Auth.headers = {};
		};

		Common.Account.getUserInfo = async () => {
			Common.Account.UserInfo = await Common.Rest.get(`${Common.Account.url}/userinfo`);
			return Common.Account.UserInfo;
		};

		Common.Account.getAuthInfo = async () => {
			Common.Account.AuthInfo = await Common.Rest.get(`${Common.Account.url}/authinfo`);
			return Common.Account.AuthInfo;
		};

		Common.Account.changePassword = async (password) => {
			return await Common.Rest.post(`${Common.Account.url}/password`, {
				username: Common.Account.UserInfo.username,
				password: password
			});
		}

		//// Common.Account.User ///////////////////
		Common.Account.readUser = async (userId) => {
			return new User(await Common.Rest.get(`${Common.Account.url}/user/${userId}`));
		};

		Common.Account.readUserByUsername = async (username) => {
			return new User(await Common.Rest.get(`${Common.Account.url}/username/${username}`));
		};

		Common.Account.searchUsers = async (search) => {
			let result = [];
			(await Common.Rest.get(`${Common.Account.url}/user${search ? "?$search=" + search : ""}`)).forEach((resource) => {
				result.push(new User(resource));
			});
			return Common.Util.setArrayFunctions(result);
		};

		Common.Account.createUser = async (username, email, firstName, lastName) => {
			return new User(await Common.Rest.post(`${Common.Account.url}/user`, {
				username: username,
				email: email,
				firstName: firstName ? firstName : username,
				lastName: lastName ? lastName : username
			}));
		};

		function User(content) {
			if (content) { Object.assign(this, content); }
			this.changePassword = async () => {
				await Common.Rest.post(`${Common.Account.url}/password`, {
					username: this.username,
					password: password
				});
				return this;
			};
			this.reload = async () => { return Object.assign(this, await Common.Rest.get(`${Common.Account.url}/user/${this.id}`)); };
			this.update = async () => { return Object.assign(this, await Common.Rest.post(`${Common.Account.url}/user/${this.id}`, this)); };
			this.delete = async () => { return await Common.Rest.delete(`${Common.Account.url}/user/${this.id}`); };
		};

		//// Common.Account.Group //////////////////
		Common.Account.readGroup = async (groupId) => {
			return new Group(await Common.Rest.get(`${Common.Account.url}/group/${groupId}`));
		};

		Common.Account.readGroupByGroupName = async (groupName) => {
			return new Group(await Common.Rest.get(`${Common.Account.url}/groupname/${groupName}`));
		};

		Common.Account.readGroupByGroupCode = async (groupCode) => {
			return new Group(await Common.Rest.get(`${Common.Account.url}/groupcode/${groupCode}`));
		};

		Common.Account.searchGroups = async (search) => {
			let result = [];
			(await Common.Rest.get(`${Common.Account.url}/group${search ? "?$search=" + search : ""}`)).forEach((resource) => {
				result.push(new Group(resource));
			});
			return Common.Util.setArrayFunctions(result);
		};

		Common.Account.createGroup = async (name, code, parentId) => {
			return new Group(await Common.Rest.post(`${Common.Account.url}/group`, {
				name: name,
				code: code,
				parentId: parentId ? parentId : undefined
			}));
		};

		function ACL(content) {
			if (content) { Object.assign(this, content); }
			this.setSref = (sref) => {
				this.sref = sref;
				return this;
			};
			this.setCRUD = (crud) => {
				this.crud = crud;
				return this;
			};
		};

		function Group(content) {
			if (content) { Object.assign(this, content); }
			this.getACLs = async () => {
				let result = [];
				(await Common.Rest.get(`${Common.Account.url}/group/${this.id}/acl`)).forEach((resource) => {
					result.push(new ACL(resource));
				});
				return Common.Util.setArrayFunctions(result);
			};
			this.updateACLs = async (aclObjs) => {
				let result = [];
				(await Common.Rest.put(`${Common.Account.url}/group/${this.id}/acl`, aclObjs)).forEach((resource) => {
					result.push(new ACL(resource));
				});
				return Common.Util.setArrayFunctions(result);
			};
			this.getUsers = async () => {
				let result = [];
				(await Common.Rest.get(`${Common.Account.url}/group/${this.id}/user`)).forEach((resource) => {
					result.push(new User(resource));
				});
				return Common.Util.setArrayFunctions(result);
			};
			this.updateUsers = async (userObjs) => {
				let result = [];
				(await Common.Rest.put(`${Common.Account.url}/group/${this.id}/user`, userObjs)).forEach((resource) => {
					result.push(new User(resource));
				});
				return Common.Util.setArrayFunctions(result);
			};
			this.reload = async () => { return Object.assign(this, await Common.Rest.get(`${Common.Account.url}/group/${this.id}`)); };
			this.update = async () => { return Object.assign(this, await Common.Rest.post(`${Common.Account.url}/group/${this.id}`, this)); };
			this.delete = async () => { return await Common.Rest.delete(`${Common.Account.url}/group/${this.id}`); };
		};

		// initialize sub modules /////////////////////////
		if (window.Module) { for (let key in window.Module) { window.Module[key].init(); }; }
		console.log("(Common) ready");
		return Common;
	}
};