const fs = require('fs');
const merge = require('lodash/merge');
const NATS = require('nats');
const shell = require('shelljs');
const uuidv4 = require('uuid/v4');

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

// Register NATS event handlers.
// TODO(JiaKuan Su): Handle following events.
nats.on('error', (err) => {
    console.error(err);
});
nats.on('connect', (nc) => {
    console.log('connected');
});
nats.on('disconnect', () => {
    console.log('disconnected');
});
nats.on('reconnecting', () => {
    console.log('reconnecting');
});
nats.on('close', () => {
    console.log('connection closed');
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
    //shell.exec(`nvidia-docker run --network="host" -e worker_id=${workerId} ${workerName}`, { async: true });
    shell.exec(`python3 /home/uniray7/Projects/jagereye/apps/tripwire/worker/worker.py ${workerId}`, {async: true});
}

// The list of active workers.
const workerList = {};

// The messaging handler from brain.
function brainHandler(msg) {
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

            createWorker(workerId, workerName);
            workerList[workerId] = {
                status: WORKER_STATUS.ACTIVE,
            }

            console.log(`Create worker (worker name=${workerName}, ID = ${workerId}) successfully`);

            break;
    }
}

nats.subscribe(CH_BRAIN_TO_RES, brainHandler);
