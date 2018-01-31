const request = require('request-promise');
const HttpStatus = require('http-status-codes');
const format = require('util').format;

const redisAsync = require('./redisAsync.js')
const {laterInMs} = require('./utils.js');

describe('Analyzer Operations: ', () => {
  describe('green path(create => start => get status => delete): ', () => {
    let analyzerId = null;
    let type = 'tripwire';
    let redisCli = null;

    beforeAll(() => {
      redisCli = new redisAsync.client();
    });

    afterAll(() => {
      redisCli.quit();
    });

    test.only('create an analyzer', async (done) => {
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
    
//    test('start the analyzer', async (done) => {
//      expect(analyzerId).not.toBeNull();
//      let options =  {
//        method: 'POST',
//        uri: 'http://localhost:5000/api/v1/analyzer/' + analyzerId + '/runtime',
//        json: true,
//        resolveWithFullResponse: true
//      };
//      let result = await request(options);
//      expect(result.statusCode).toBe(HttpStatus.CREATED);
//
//      expect(result).toHaveProperty('body');
//      expect(result.body).toHaveProperty('code');
//      expect(result.body).toHaveProperty('type');
//      expect(result.body).toHaveProperty('status');
//      expect(result.body.status).toBe('CREATE');
//
//      await laterInMs(6000);
//      // check the record in db and get the workerId
//      workerId = await redisAsync.get(format('%s:anal:%s', type, analyzerId));
//      expect(workerId).not.toBeNull();
//
//      workerStatus = await redisAsync.get(format('%s:worker:%s:status', type, workerId));
//      console.log(workerStatus)
//
//
//
//      workerHBeat = await redisAsync.get(format('%s:worker:%s:hbeat', type, workerId));
//      expect(workerHBeat).not.toBeNull();
//      workerHBeat = parseInt(workerHBeat);
//      timestamp = (new Date().getTime() / 1000)
//
//      console.log(workerHBeat)
//      console.log(timestamp)
//      expect(timestamp-workerHBeat).toBeLessThan(5);
//      // check the container is running
//      done();
//    }, 10000);
//    // ----- test('start the analyzer')
    
  });

  //describe('create & start an analyzer: ', () => {});
  //describe('start an analyzer which triggers events: ', () => {
  //  test('hello')
  //})

  //describe('get status: ', () => {
  //  test('hello')


  //})

  //describe('stop the analyzer: ', () => {
  //  test('hello')


  //})

});
