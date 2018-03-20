const redis = require('redis');
const {promisify} = require('util');

class client{
  constructor(host) {
    this.client = redis.createClient(host);
  }

  async get(key) {
    const getAsync = promisify(this.client.get).bind(this.client);
    return await getAsync(key);
  }
 
  quit() {
    this.client.quit();
  }
}

module.exports = {client: client};
