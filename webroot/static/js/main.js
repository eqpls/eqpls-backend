// javascript here

Common.init(async () => { // main task

	// auth example ///////////////////////////////////////////////
	console.log("AUTH EXAMPLE");
	document.getElementById("eqpls-access-token").innerText = Common.Auth.accessToken;
	console.log(Common.Account.UserInfo);
	console.log(await Common.Account.getUsers());
	/*
	let role = await new Common.Auth.Role({
		name: "testRole"
	}).createModel();
	console.log(role);

	let group = await new Common.Auth.Group({
		name: "testGroup"
	}).createModel();
	console.log(group);

	let account = await Common.Auth.searchAccount({
		$filter: `username:${Common.Auth.username}`
	});
	account = account[0];
	console.log(account);
	account.roles.push(role.id);
	account.groups.push(group.id);
	await account.updateModel();

	account = await Common.Auth.readAccount(account.id)
	console.log(account);
	await Common.Auth.checkUserInfo();
	console.log(Common.Auth.UserInfo);

	account.roles.pop(role.id);
	account.groups.pop(group.id);
	await account.updateModel();

	await role.deleteModel();
	await group.deleteModel();
	*/

	// db example /////////////////////////////////////////////////
	/*
	console.log("DB EXAMPLE");
	let id = Common.Util.getUUID()
	let sampleData = {
		text: "Hello World !!!",
		user: Common.Auth.username
	}
	await Common.DB.EP.Temp.write(id, sampleData);
	console.log(await Common.DB.EP.Temp.readAll());
	sampleData = await Common.DB.EP.Temp.read(id);
	console.log(sampleData);
	sampleData.text = "Nice to meet you !!!";
	await Common.DB.EP.Temp.write(id, sampleData);
	console.log(await Common.DB.EP.Temp.readAll());
	console.log(await Common.DB.EP.Temp.read(id));
	await Common.DB.EP.Temp.delete(id);
	console.log(await Common.DB.EP.Temp.readAll());
	console.log(await Common.DB.EP.Temp.read(id));
	*/

	// obj store example //////////////////////////////////////////
	/*
	console.log("OBJ STORE EXAMPLE");
	let buckets = await Module.Data.getBuckets();
	console.log(buckets);
	if (!Common.Auth.UserInfo.Groups.empty()) {
		for (let i = 0; i < Common.Auth.UserInfo.Groups.len(); i++) {
			try { await Module.Data.createGroupBucket(Common.Auth.UserInfo.Groups[i], `myGroupBucket ${i}`); } // create group bucket without guota
			catch (e) {} // default user group can not create bucket
		}
	}
	await Module.Data.createUserBucket("myBucket", 1); // create private bucket with 1GB quota

	buckets = await Module.Data.getBuckets();
	console.log("before deleted", buckets);
	for (let i = 0; i < buckets.group.len(); i++) {
		let bucket = buckets.group[i];
		let nodes = await bucket.getNodes();
		console.log(nodes);
		await bucket.delete();
	}
	for (let i = 0; i < buckets.user.len(); i++) {
		let bucket = buckets.user[i];
		let nodes = await bucket.getNodes();
		console.log(nodes);
		await bucket.delete();
	}
	buckets = await Module.Data.getBuckets();
	console.log("after deleted", buckets);
	*/

	// websock example ////////////////////////////////////////////
	Common.WSock.connect(
		"/router/v1/websocket", // wsock url
		async (socket, data) => { // receiver
			console.log(JSON.parse(data), socket); // echo msg from server
		},
		async (socket) => { // initiator
		}
	);
}).login();