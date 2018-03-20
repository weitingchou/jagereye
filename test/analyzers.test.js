const request = require('request-promise');
const HttpStatus = require('http-status-codes');
const WebSocket = require('ws');
const MongoClient = require('mongodb').MongoClient;
const Docker = require('dockerode');
const dockerCli = new Docker();

const format = require('util').format;

const redisAsync = require('./redisAsync.js');
const {laterInMs} = require('./utils.js');
const video = require('./videos/app.js');

const START_TIMEOUT = 6500;
const DELETE_TIMEOUT = 6000;
const HBEAT_TIMEOUT = 4000;
const MAX_TIMEOUT = 15000;

const videoAppPort = 8081;

describe('Analyzer Operations: ', () => {
  describe('green path(create => start => get status => delete): ', () => {
    let analyzerId = null;
    let type = 'tripwire';
    let redisCli = null;
    let mongoCli = null;
    let videoApp = null;
    let testStartTime = (new Date().getTime() / 1000)

    beforeAll(async () => {
      videoApp = new video.videoApp(videoAppPort);
      videoApp.start();

      redisCli = new redisAsync.client();

      mongoConn = await MongoClient.connect('mongodb://localhost:27017');
      const mongoDB = mongoConn.db('jager_test');
      const coll = mongoDB.collection('analyzers');
      mongoCli = mongoConn;
      await coll.remove({});
      mongoConn.close();
      return;
    });

    afterAll(() => {
      videoApp.stop();
      redisCli.quit();
    });

    test('create an analyzer', async (done) => {
      let postData = {
        "name": "Front Gate 1",
        "type": type,
        "enabled": true,
        "source": {
          "mode": "stream",
          "url": "http://localhost:"+videoAppPort+"/video.mp4"
        },
        "pipelines": [
          {
            "name": "tripwire",
            "params": {
              "region": [
                {
                  "x": 800,
                  "y": 100
                },
                {
                  "x": 1000,
                  "y": 700
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

    test('wait for notification', async (done) => {
      let ws = new WebSocket('ws://localhost:5000/notification');
      ws.on('message', function incoming(data) {
        try {
          data = data.replace(/'/g, '"');
          data = JSON.parse(data);
          let notifiedInfo = data[0];
          expect(notifiedInfo).toHaveProperty('timestamp');
          expect(notifiedInfo).toHaveProperty('analyzerId');
          expect(notifiedInfo.analyzerId).toEqual(analyzerId);
          expect(notifiedInfo).toHaveProperty('type');
          expect(notifiedInfo.type).toEqual('tripwire_alert');
          expect(notifiedInfo).toHaveProperty('appName');
          expect(notifiedInfo.appName).toEqual(type);
          expect(notifiedInfo).toHaveProperty('content');
          expect(notifiedInfo.content).toHaveProperty('triggered');
          expect(notifiedInfo.content.triggered).toContain('person');
          expect(notifiedInfo.content).toHaveProperty('thumbnail_name');
          expect(notifiedInfo.content).toHaveProperty('video_name');
          expect(notifiedInfo).toHaveProperty('date');
        } catch (err) {
          expect(err).toBeNull();
        } finally {
          ws.close();
          done();
        };
      });

    }, MAX_TIMEOUT);
    // ----- test('wait for events')

    test('query events', async (done) => {
      let now = (new Date().getTime() / 1000)
      let postData = {
        timestamp: {
          start: testStartTime,
          end: now
        },
        analyzers: [analyzerId]
      };

      let options =  {
        method: 'POST',
        uri: 'http://localhost:5000/api/v1/events',
        body: postData,
        json: true,
        resolveWithFullResponse: true
      };
      let result = await request(options);
      expect(result.statusCode).toBe(HttpStatus.OK);
      expect(result).toHaveProperty('body');

      let eventInfo = result.body[0];
      expect(eventInfo).toHaveProperty('timestamp');
      expect(eventInfo).toHaveProperty('analyzerId');
      expect(eventInfo.analyzerId).toBe(analyzerId);
      expect(eventInfo).toHaveProperty('type');
      expect(eventInfo).toHaveProperty('appName');
      expect(eventInfo).toHaveProperty('content');
      expect(eventInfo).toHaveProperty('type');

      done();
    });
    // ----- test('query events')

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
