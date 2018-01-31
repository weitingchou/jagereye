const request = require('request-promise');
const HttpStatus = require('http-status-codes');
const MongoClient = require('mongodb').MongoClient;
const Docker = require('dockerode');
const dockerCli = new Docker();

const format = require('util').format;

const redisAsync = require('./redisAsync.js')
const {laterInMs} = require('./utils.js');

START_TIMEOUT = 6000;
DELETE_TIMEOUT = 5000;
HBEAT_TIMEOUT = 4000;

MAX_TIMEOUT = 8000;

describe('Analyzer Operations: ', () => {
  describe('green path(create => start => get status => delete): ', () => {
    let analyzerId = null;
    let type = 'tripwire';
    let redisCli = null;
    let mongoCli = null;

    beforeAll(() => {
      redisCli = new redisAsync.client();

      return MongoClient.connect('mongodb://localhost:27017/jager_test')
        .then((db) => {
          mongoCli = db;
          let analyzer_col = db.collection('analyzers');
          return analyzer_col.remove({});
        });
    });

    afterAll(() => {
      redisCli.quit();
      mongoCli.close();
    });

    test('create an analyzer', async (done) => {
      let postData = {
        "name": "Front Gate 1",
        "type": type,
        "enabled": true,
        "source": {
          "mode": "stream",
          "url": "http://10.10.0.4/video.mjpg"
        },
        "pipelines": [
          {
            "name": "tripwire",
            "params": {
              "region": [
                {
                  "x": 0,
                  "y": 0
                },
                {
                  "x": 200,
                  "y": 200
                }
              ],
              "triggers": [
                "person"
              ]
            }
          }
        ]
      };
      let options =  {
        method: 'POST',
        uri: 'http://localhost:5000/api/v1/analyzers',
        body: postData,
        json: true,
        resolveWithFullResponse: true
      };
      let result = await request(options);
      expect(result.statusCode).toBe(HttpStatus.CREATED);
      expect(result).toHaveProperty('body');
      expect(result.body).toHaveProperty('id');
      analyzerId = result.body.id;
      done();
    });
    // ----- test('create analyzer')
    
    test('start the analyzer', async (done) => {
      expect(analyzerId).not.toBeNull();
      let options =  {
        method: 'POST',
        uri: 'http://localhost:5000/api/v1/analyzer/' + analyzerId + '/runtime',
        json: true,
        resolveWithFullResponse: true
      };
      let result = await request(options);
      expect(result.statusCode).toBe(HttpStatus.CREATED);

      expect(result).toHaveProperty('body');
      expect(result.body).toHaveProperty('code');
      expect(result.body).toHaveProperty('type');
      expect(result.body).toHaveProperty('status');
      expect(result.body.status).toBe('CREATE');

      await laterInMs(START_TIMEOUT);

      // check the workerId of the analyzer exist
      let workerId = await redisCli.get(format('%s:anal:%s', type, analyzerId));
      expect(workerId).not.toBeNull();

      // check the worker status
      let workerStatus = await redisCli.get(format('%s:worker:%s:status', type, workerId));
      expect(workerStatus).toBe('RUNNING');

      // check the heartbeat is close to now()
      let workerHBeat = await redisCli.get(format('%s:worker:%s:hbeat', type, workerId));
      expect(workerHBeat).not.toBeNull();
      workerHBeat = parseInt(workerHBeat);
      let timestamp = (new Date().getTime() / 1000)
      expect(timestamp-workerHBeat).toBeLessThan(HBEAT_TIMEOUT/1000);

      // check the container is running
      let container  =  dockerCli.getContainer(workerId);
      let inspect = await container.inspect();
      let state = inspect.State;
      expect(state.Running).toBe(true);
      done();
    }, MAX_TIMEOUT);
    // ----- test('start the analyzer')
 
    test('get status of the analyzer', async (done) => {
      expect(analyzerId).not.toBeNull();

      let options =  {
        method: 'GET',
        uri: 'http://localhost:5000/api/v1/analyzer/' + analyzerId + '/runtime',
        json: true,
        resolveWithFullResponse: true
      };
      let result = await request(options);
      expect(result.statusCode).toBe(HttpStatus.OK);
      expect(result).toHaveProperty('body');
      expect(result.body).toHaveProperty('code');
      expect(result.body.code).toBe('reply analyzer status');
      expect(result.body).toHaveProperty('type');
      expect(result.body.type).toBe(type);
      expect(result.body).toHaveProperty('status');
      expect(result.body.status).toBe('RUNNING');

      done();
    });
    // ----- test('get status of the analyzer')

    test('delete the analyzer', async (done) => {
      let options =  {
        method: 'DELETE',
        uri: 'http://localhost:5000/api/v1/analyzer/' + analyzerId,
        json: true,
        resolveWithFullResponse: true
      };
      let result = await request(options);
      expect(result.statusCode).toBe(HttpStatus.OK);
      expect(result).toHaveProperty('body');
      expect(result.body).toHaveProperty('result');
      expect(result.body.result.id).toBe(analyzerId);
      done();
    }, DELETE_TIMEOUT);
    // ----- test('delete the analyzer')
  });
});
