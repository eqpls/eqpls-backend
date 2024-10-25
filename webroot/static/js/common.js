window.Common = window.Common || {
	init: (main) => {
		console.log("(Common) start");

		// Common definitions /////////////////////////////
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
					setTimeout(()=> {Common.WSock.connect(url, receiver, initiator, closer);}, 2000);
					if (closer) { closer(event); }
				};
				return socket;
			} catch (e) {
				setTimeout(()=> {Common.WSock.connect(url, receiver, initiator, closer);}, 2000);
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
						main();
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

		//// Common.Account interfaces /////////////
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
			await main();
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

		Common.Account.getUsers = async (search) => {
			return await Common.Rest.get(`${Common.Account.url}/users${search?"?search="+search:""}`);
		};







		//// Common.Auth model interfaces //////////
		/*
		Common.getSchema = async () => { return Common.Rest.get(`${Common.uerpUrl}/schema`).then((content) => { return content; }); };

		Common.Auth.readOrg = async (id) => { return Common.Rest.get(`${Common.uerpUrl}/common/auth/org/${id}`).then((content) => { return new Org(content); }); };
		Common.Auth.countOrg = async (query) => {
			if (query) {
				let qstr = []
				for (let key in query) { qstr.push(`${key}=${query[key]}`); }
				query = `?${qstr.join("&")}`;
			} else { query = ""; }
			return Common.Rest.get(`${Common.uerpUrl}/common/auth/org/count${query}`).then((content) => { return content });
		};
		Common.Auth.searchOrg = async (query) => {
			if (query) {
				let qstr = []
				for (let key in query) { qstr.push(`${key}=${query[key]}`); }
				query = `?${qstr.join("&")}`;
			} else { query = ""; }
			return Common.Rest.get(`${Common.uerpUrl}/common/auth/org${query}`).then((contents) => {
				let results = [];
				contents.forEach((content) => { results.push(new Org(content)); });
				return Common.Util.setArrayFunctions(results);
			});
		};
		function Org(content) {
			if (content) { Object.assign(this, content); }
			this.reloadModel = async () => { return Common.Rest.get(this.uref).then((content) => { Object.assign(this, content); return this; }); };
			this.createModel = async () => { return Common.Rest.post(`${Common.uerpUrl}/common/auth/org`, this).then((content) => { Object.assign(this, content); return this; }); };
			this.updateModel = async () => { return Common.Rest.put(this.uref, this).then((content) => { Object.assign(this, content); return this; }); };
			this.deleteModel = async () => { return Common.Rest.delete(this.uref).then((content) => { return content; }); };
			this.print = () => { console.log(this); };
		};
		Common.Auth.Org = Org;

		Common.Auth.readRole = async (id) => { return Common.Rest.get(`${Common.uerpUrl}/common/auth/role/${id}`).then((content) => { return new Role(content); }); };
		Common.Auth.countRole = async (query) => {
			if (query) {
				let qstr = []
				for (let key in query) { qstr.push(`${key}=${query[key]}`); }
				query = `?${qstr.join("&")}`;
			} else { query = ""; }
			return Common.Rest.get(`${Common.uerpUrl}/common/auth/role/count${query}`).then((content) => { return content });
		};
		Common.Auth.searchRole = async (query) => {
			if (query) {
				let qstr = []
				for (let key in query) { qstr.push(`${key}=${query[key]}`); }
				query = `?${qstr.join("&")}`;
			} else { query = ""; }
			return Common.Rest.get(`${Common.uerpUrl}/common/auth/role${query}`).then((contents) => {
				let results = [];
				contents.forEach((content) => { results.push(new Role(content)); });
				return Common.Util.setArrayFunctions(results);
			});
		};
		function Role(content) {
			if (content) { Object.assign(this, content); }
			this.reloadModel = async () => { return Common.Rest.get(this.uref).then((content) => { Object.assign(this, content); return this; }); };
			this.createModel = async () => { return Common.Rest.post(`${Common.uerpUrl}/common/auth/role`, this).then((content) => { Object.assign(this, content); return this; }); };
			this.updateModel = async () => { return Common.Rest.put(this.uref, this).then((content) => { Object.assign(this, content); return this; }); };
			this.deleteModel = async () => { return Common.Rest.delete(this.uref).then((content) => { return content; }); };
			this.print = () => { console.log(this); };
		};
		Common.Auth.Role = Role;

		Common.Auth.readGroup = async (id) => { return Common.Rest.get(`${Common.uerpUrl}/common/auth/group/${id}`).then((content) => { return new Group(content); }); };
		Common.Auth.countGroup = async (query) => {
			if (query) {
				let qstr = []
				for (let key in query) { qstr.push(`${key}=${query[key]}`); }
				query = `?${qstr.join("&")}`;
			} else { query = ""; }
			return Common.Rest.get(`${Common.uerpUrl}/common/auth/group/count${query}`).then((content) => { return content });
		};
		Common.Auth.searchGroup = async (query) => {
			if (query) {
				let qstr = []
				for (let key in query) { qstr.push(`${key}=${query[key]}`); }
				query = `?${qstr.join("&")}`;
			} else { query = ""; }
			return Common.Rest.get(`${Common.uerpUrl}/common/auth/group${query}`).then((contents) => {
				let results = [];
				contents.forEach((content) => { results.push(new Group(content)); });
				return Common.Util.setArrayFunctions(results);
			});
		};
		function Group(content) {
			if (content) { Object.assign(this, content); }
			this.reloadModel = async () => { return Common.Rest.get(this.uref).then((content) => { Object.assign(this, content); return this; }); };
			this.createModel = async () => { return Common.Rest.post(`${Common.uerpUrl}/common/auth/group`, this).then((content) => { Object.assign(this, content); return this; }); };
			this.updateModel = async () => { return Common.Rest.put(this.uref, this).then((content) => { Object.assign(this, content); return this; }); };
			this.deleteModel = async () => { return Common.Rest.delete(this.uref).then((content) => { return content; }); };
			this.print = () => { console.log(this); };
		};
		Common.Auth.Group = Group;

		Common.Auth.readAccount = async (id) => { return Common.Rest.get(`${Common.uerpUrl}/common/auth/account/${id}`).then((content) => { return new Account(content); }); };
		Common.Auth.countAccount = async (query) => {
			if (query) {
				let qstr = []
				for (let key in query) { qstr.push(`${key}=${query[key]}`); }
				query = `?${qstr.join("&")}`;
			} else { query = ""; }
			return Common.Rest.get(`${Common.uerpUrl}/common/auth/account/count${query}`).then((content) => { return content });
		};
		Common.Auth.searchAccount = async (query) => {
			if (query) {
				let qstr = []
				for (let key in query) { qstr.push(`${key}=${query[key]}`); }
				query = `?${qstr.join("&")}`;
			} else { query = ""; }
			return Common.Rest.get(`${Common.uerpUrl}/common/auth/account${query}`).then((contents) => {
				let results = [];
				contents.forEach((content) => { results.push(new Account(content)); });
				return Common.Util.setArrayFunctions(results);
			});
		};
		function Account(content) {
			if (content) { Object.assign(this, content); }
			this.reloadModel = async () => { return Common.Rest.get(this.uref).then((content) => { Object.assign(this, content); return this; }); };
			this.createModel = async () => { return Common.Rest.post(`${Common.uerpUrl}/common/auth/account`, this).then((content) => { Object.assign(this, content); return this; }); };
			this.updateModel = async () => { return Common.Rest.put(this.uref, this).then((content) => { Object.assign(this, content); return this; }); };
			this.deleteModel = async () => { return Common.Rest.delete(this.uref).then((content) => { return content; }); };
			this.print = () => { console.log(this); };
		};
		Common.Auth.Account = Account;

		*/

		// initialize sub modules /////////////////////////
		if (window.Module) { for (let key in window.Module) { window.Module[key].init(); }; }
		console.log("(Common) ready");
		return Common;
	}
};