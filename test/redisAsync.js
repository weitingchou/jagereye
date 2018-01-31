let redis = require("redis");
let {promisify} = require('util');

class client{
  constructor(host) {
    this.client = redis.createClient();
  }

  async get(key) {
    let getAsync = promisify(client.get).bind(client);
    return await getAsync(key);
  }
 
  quit() {
    this.client.quit();
  }
}

module.exports = {client: client};
