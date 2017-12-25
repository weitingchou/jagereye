const fs = require('fs');
const merge = require('lodash/merge');
const NATS = require('nats');
const Promise = require('bluebird');
const redis = require('redis');
const shell = require('shelljs');
const uuidv4 = require('uuid/v4');

Promise.promisifyAll(redis.RedisClient.prototype);
Promise.promisifyAll(redis.Multi.prototype);

// Channels for worker and resource manager.
const CH_BRAIN_TO_RES = 'ch_brain_res';
const CH_RES_TO_BRAIN = 'ch_res_brain';

// The possible worker status.
const WORKER_STATUS = {
    ACTIVE: 'ACTIVE',
};

// The Messaging format.
const MESSAGING = JSON.parse(fs.readFileSync('../messaging.json', 'utf8'));

// Initialize NATS.
const nats = NATS.connect({
    maxReconnectAttempts: -1,
    reconnectTimeWait: 250,
});

// Initialize memory database client.
const mem_db_cli = redis.createClient();

// Register NATS event handlers.
// TODO(JiaKuan Su): Handle following events.
nats.on('error', (err) => {
    console.error(err);
});
nats.on('connect', (nc) => {
    console.log('NATS connected.');
});
nats.on('disconnect', () => {
    console.log('NATS disconnected.');
});
nats.on('reconnecting', () => {
    console.log('NATS reconnecting.');
});
nats.on('close', () => {
    console.log('NATS connection closed.');
});

// Register memory database client event handlers.
// TODO(JiaKuan Su): Handle following events.
mem_db_cli.on('error', (err) => {
    console.error(err);
});
mem_db_cli.on('ready', () => {
    console.log('Memory database ready.');
});
mem_db_cli.on('connect', () => {
    console.log('Memory database connected.');
});
mem_db_cli.on('reconnecting', () => {
    console.log('Memory database reconnecting.');
});
mem_db_cli.on('end', () => {
    console.log('Memory database end.');
});
mem_db_cli.on('warning', () => {
    console.log('Memory database warning.');
});

// Generate a unique worker ID.
function genWorkerId() {
    return `worker_${uuidv4()}`;
}

// Create a worker.
function createWorker(workerId, workerName) {
    // TODO(JiaKuan Su): Currently we must use nvidia-docker to create workers,
    // Please use normal docker instead of nvidia-docker after the GPU is split
    // from workers.
    shell.exec(`nvidia-docker run --network="host" -e worker_id=${workerId} ${workerName}`, { async: true });
}

// The messaging handler from brain.
async function brainHandler(msg) {
    console.log(`Request from brain: ${msg}`);

    const request = JSON.parse(msg.replace(/'/g, '"'));
    // Parse the command.
    const { command } = request;

    switch (command) {
        case MESSAGING[CH_BRAIN_TO_RES]['CREATE_WORKER']:
            const {
                workerName,
            } = request.params;
            const workerId = genWorkerId();
            // The Replied information to brain.
            const reply = JSON.stringify(merge({}, request, {
                response: {
                    workerId,
                },
            }));

            console.log(`Response to brain: ${reply}`);

            // Reply to brain.
            nats.request(CH_RES_TO_BRAIN, reply);
            // Create a worker.
            createWorker(workerId, workerName);
            // Update worker status
            const workerKey = `res_mgr:worker:${workerId}`;
            const workerInfo = JSON.stringify({
                status: WORKER_STATUS.ACTIVE,
            });
            try {
                await mem_db_cli.setAsync(workerKey, workerInfo);
                console.log(`Create worker (worker name=${workerName}, ID = ${workerId}) successfully`);
            } catch (e) {
                // TODO(JiaKuan Su): Error handling.
                console.error(e);
            }

            break;
    }
}

nats.subscribe(CH_BRAIN_TO_RES, brainHandler);
