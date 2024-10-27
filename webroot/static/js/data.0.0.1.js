window.Module = window.Module || {};
window.Module.Data = window.Module.Data || {
	init: () => {
		Module.Data.url = `${Common.url}/minio/api/v1`;
		Module.Data.moduleUrl = `${Common.url}/data/v1`;
		Module.Data.isAutoLogin = true;
		console.log("(Module.Data) start");
		Module.Data.login = () => {
			fetch(`${Module.Data.url}/login`).then((res) => {
				if (res.ok) { return res.json(); }
				throw res;
			}).then((data) => {
				fetch(data.redirectRules[0].redirect).then((res) => {
					if (res.ok) { return res.json(); }
					throw res;
				}).then((data) => {
					data.state = decodeURIComponent(data.state);
					fetch(`${Module.Data.url}/login/oauth2/auth`, {
						method: "POST",
						headers: { "Content-Type": "application/json" },
						body: JSON.stringify(data)
					}).then((res) => {
						if (res.ok) {
							Module.Data.getGroupBuckets = async () => {
								let result = [];
								let resources = await Common.Rest.get(`${Common.Uerp.url}/data/groupbucket`);
								resources.forEach((resource) => { result.push(new Bucket(resource)); });
								return Common.Util.setArrayFunctions(result);
							};
							Module.Data.getUserBuckets = async () => {
								let result = [];
								let resources = await Common.Rest.get(`${Common.Uerp.url}/data/userbucket?$size=20`);
								resources.forEach((resource) => { result.push(new Bucket(resource)); });
								return Common.Util.setArrayFunctions(result);
							};
							Module.Data.createGroupBucket = async (groupObj, displayName, quota) => {
								return new Bucket(await Common.Rest.post(`${Module.Data.moduleUrl}/data/groupbucket?$publish&$group=${groupObj.code}`, {
									displayName: displayName,
									quota: quota ? parseInt(quota) : 0
								}));
							};
							Module.Data.createUserBucket = async (displayName, quota) => {
								return new Bucket(await Common.Rest.post(`${Module.Data.moduleUrl}/data/userbucket?$publish`, {
									displayName: displayName,
									quota: quota ? parseInt(quota) : 0
								}));
							};
							Module.Data.getAccessKeys = async () => {
								return fetch(`${Module.Data.url}/service-accounts`).then((res) => {
									if (res.ok) { return res.json(); }
									throw res;
								}).then((data) => {
									let result = [];
									data.forEach((content) => {
										content.policy = content.policy || "";
										content.expiry = content.expiry || null;
										content.status = content.accountStatus;
										result.push(new AccessKey(content));
									});
									return Common.Util.setArrayFunctions(result);
								});
							};
							Module.Data.createAccessKey = async (name, description, policy, expiry, status) => {
								if (!name) { throw "(module.data.createAccessKey) parameter is required"; }
								description = description || "";
								policy = policy || "";
								expiry = expiry || null;
								status = status || "on";
								let secretKey = Common.Util.getRandomString(40);
								return fetch(`${Module.Data.url}/service-account-credentials`, {
									method: "POST",
									headers: { "Content-Type": "application/json" },
									body: JSON.stringify({
										name: name,
										description: description,
										policy: policy,
										expiry: expiry,
										status: status,
										accessKey: Common.Util.getRandomString(20),
										secretKey: secretKey
									})
								}).then((res) => {
									if (res.ok) { return res.json(); }
									throw res;
								}).then((data) => {
									let key = new AccessKey(data);
									key.secretKey = secretKey;
									return key;
								});
							};
						} else { throw res; }
					});
				});
			});
		};

		function AccessKey(content) {
			if (content) { Object.assign(this, content); }
			this.reload = async () => {
				return Object.assign(this, fetch(`${Module.Data.url}/service-accounts/${Common.Util.utoa(this.accessKey)}`).then((res) => {
					if (res.ok) { return true; }
					throw res;
				}));
			};
			this.delete = async () => {
				return fetch(`${Module.Data.url}/service-accounts/${Common.Util.utoa(this.accessKey)}`, {
					method: "DELETE"
				}).then((res) => {
					if (res.ok) { return true; }
					throw res;
				});
			};
		};

		function Bucket(content) {
			if (content) { Object.assign(this, content); }
			this.getNodes = async () => {
				return fetch(`${Module.Data.url}/buckets/${this.externalId}/objects`).then((res) => {
					if (res.ok) { return res.json(); }
					throw res;
				}).then((data) => {
					let folders = [];
					let files = [];
					if (data.objects) {
						data.objects.forEach((content) => {
							content.bucket = this;
							content.parent = this;
							if (content.etag) { files.push(new File(content)); }
							else { folders.push(new Folder(content)); }
						});
					}
					return {
						folders: Common.Util.setArrayFunctions(folders),
						files: Common.Util.setArrayFunctions(files)
					};
				});
			};
			this.upload = async (files) => {
				let results = [];
				if (files.length > 0) {
					let coros = [];
					for (let i = 0; i < files.length; i++) {
						let file = files[i];
						let form = new FormData();
						form.append(file.size, file);
						coros.push(fetch(`${Module.Data.url}/buckets/${this.bucket.externalId}/objects/upload?prefix=${Common.Util.utoa(file.name)}`, {
							method: "POST",
							body: form
						}));
						results.push(null);
					}
					for (let i = 0, j = 1; i < files.length; i++, j++) {
						let coro = coros[i];
						coro.then((res) => { results[i] = res; });
					}
				}
				return results;
			};
			this.reload = async () => {
				switch (this.sref) {
					case "data.GroupBucket": return Object.assign(this, await Common.Rest.get(`${Module.Data.moduleUrl}/data/groupbucket/${this.id}`));
					case "data.UserBucket": return Object.assign(this, await Common.Rest.get(`${Module.Data.moduleUrl}/data/userbucket/${this.id}`));
				};
				throw "could not aware bucket type";
			};
			this.update = async () => {
				switch (this.sref) {
					case "data.GroupBucket": return Object.assign(this, await Common.Rest.put(`${Module.Data.moduleUrl}/data/groupbucket/${this.id}?$publish`, this));
					case "data.UserBucket": return Object.assign(this, await Common.Rest.put(`${Module.Data.moduleUrl}/data/userbucket/${this.id}?$publish`, this));
				};
				throw "could not aware bucket type";
			};
			this.delete = async () => {
				switch (this.sref) {
					case "data.GroupBucket": return await Common.Rest.delete(`${Module.Data.moduleUrl}/data/groupbucket/${this.id}?$publish`);
					case "data.UserBucket": return await Common.Rest.delete(`${Module.Data.moduleUrl}/data/userbucket/${this.id}?$publish`);
				};
				throw "could not aware bucket type";
			};
			this.print = () => { console.log(this); };
		};

		function Folder(content) {
			if (content) { Object.assign(this, content); }
			this.getNodes = async () => {
				return fetch(`${Module.Data.url}/buckets/${this.bucket.externalId}/objects?prefix=${Common.Util.utoa(this.name)}`).then((res) => {
					if (res.ok) { return res.json(); }
					throw res;
				}).then((data) => {
					let folders = [];
					let files = [];
					if (data.objects) {
						data.objects.forEach((content) => {
							content.bucket = this.bucket;
							content.parent = this;
							if (content.etag) { files.push(new File(content)); }
							else { folders.push(new Folder(content)); }
						});
					}
					return {
						folders: Common.Util.setArrayFunctions(folders),
						files: Common.Util.setArrayFunctions(files)
					};
				});
			};
			this.getParent = async () => { return this.parent; };
			this.createFolder = async (name) => {
				return new Folder({
					last_modified: "",
					name: `${this.name}${name}/`,
					bucket: this.bucket
				});
			};
			this.upload = async (files) => {
				let results = [];
				if (files.length > 0) {
					let coros = [];
					for (let i = 0; i < files.length; i++) {
						let file = files[i];
						let prefix = `${this.name}${file.name}`;
						let form = new FormData();
						form.append(file.size, file);
						coros.push(fetch(`${Module.Data.url}/buckets/${this.bucket.externalId}/objects/upload?prefix=${Common.Util.utoa(prefix)}`, {
							method: "POST",
							body: form
						}));
						results.push(null);
					}
					for (let i = 0, j = 1; i < files.length; i++, j++) {
						let coro = coros[i];
						coro.then((res) => { results[i] = res; });
					}
				}
				return results;
			};
			this.reload = async () => {
				return Object.assign(this, fetch(`${Module.Data.url}/buckets/${this.bucket.externalId}/objects?prefix=${Common.Util.utoa(this.name)}`).then((res) => {
					if (res.ok) { return res.json(); }
					throw res;
				}).then((data) => {
					return data;
				}));
			};
			this.delete = async () => {
				return fetch(`${Module.Data.url}/buckets/${this.bucket.externalId}/objects?prefix=${Common.Util.utoa(this.name)}&recursive=true`, {
					method: "DELETE"
				}).then((res) => {
					if (res.ok) { return true; }
					throw res;
				});
			};
			this.print = () => { console.log(this); };
		};

		function File(content) {
			if (content) { Object.assign(this, content); }
			this.getParent = async () => { return this.parent; };
			this.load = async () => {
				let data = await Common.DB.Blob.index.read(this.etag)
				if (data) { return data.blob; }
				blob = await fetch(`${Module.Data.url}/buckets/${this.bucket.externalId}/objects/download?prefix=${Common.Util.utoa(this.name)}`).then((res) => {
					if (res.ok) { return res.blob(); }
					throw res;
				});
				await Common.DB.Blob.index.write(this.etag, { blob: blob });
				return blob;
			};
			this.download = async () => {
				let blob = await this.load();
				let dom = document.createElement("a");
				let fileName = this.name.split("/");
				let url = URL.createObjectURL(blob);
				dom.href = url;
				dom.download = fileName[fileName.length - 1];
				dom.click();
				dom.remove();
				URL.revokeObjectURL(url);
				return blob;
			};
			this.reload = async () => {
				return Object.assign(this, fetch(`${Module.Data.url}/buckets/${this.bucket.externalId}/objects?prefix=${Common.Util.utoa(this.name)}`).then((res) => {
					if (res.ok) { return res.json(); }
					throw res;
				}).then((data) => {
					return data;
				}));
			};
			this.delete = async () => {
				await Common.DB.Blob.index.delete(this.etag);
				return fetch(`${Module.Data.url}/buckets/${this.bucket.externalId}/objects?prefix=${Common.Util.utoa(this.name)}`, {
					method: "DELETE"
				}).then((res) => {
					if (res.ok) { return true; }
					throw res;
				});
			};
			this.print = () => { console.log(this); };
		};

		console.log("(Module.Data) ready");
		return Module.Data;
	}
};
