const Docker = require('dockerode');
const fs = require('fs');
const map = require('lodash/map');
const merge = require('lodash/merge');
const NATS = require('nats');
const Promise = require('bluebird');
const redis = require('redis');
const shell = require('shelljs');
const uuidv4 = require('uuid/v4');
const yaml = require('read-yaml')

Promise.promisifyAll(redis.RedisClient.prototype);
Promise.promisifyAll(redis.Multi.prototype);

// Channels for worker and resource manager.
const CH_BRAIN_TO_RES = 'ch_brain_res';
const CH_RES_TO_BRAIN = 'ch_res_brain';

// The shared directory between host and containers.
const SHARED_ROOT =
    process.env.SHARED_ROOT ?
    process.env.SHARED_ROOT :
    process.env.HOME;
const HOST_SHARED_DIR = `${SHARED_ROOT}/jagereye_shared`;
const CONTAINER_SHARED_DIR = '/root/jagereye_shared';

const CONFIG = yaml.sync('./config.yml');

// The possible worker status.
const WORKER_STATUS = {
    CREATING: 'CREATING',
    RUNNING: 'RUNNING',
    REMOVED: 'REMOVED',
};

// The Messaging format.
const MESSAGING = JSON.parse(fs.readFileSync('../../shared/messaging.json', 'utf8'));

// Initialize Docker.
const docker = new Docker({
    Promise,
});

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

// Check whether a worker name exists or not.
function hasWorkerName(workerName) {
    const params = { silent: true };
    const {
        stdout,
    } = shell.exec(`docker images -q ${workerName} 2> /dev/null`, params);
    return stdout !== '';
}

// Check whether the system has enough resource to lauch a new worker.
function hasEnoughResource() {
    // TODO(JiaKuan Su): Implement it.
    return true;
}

// Create a worker.
async function createWorker(workerId, workerName) {
    // TODO: Read the network mode configuration from 'shared/config.*.yml' instead
    //       of hardcoded '--network="host"'.
    const params = {
        LogConfig: {
            Type:'syslog',
                Config:{
                    'syslog-address': 'udp://'+CONFIG.logging.syslog.host+':'+CONFIG.logging.syslog.port,
                    'syslog-facility': 'local1',
                    'tag': workerId + ' - thrid-party pid:'
                }
        },
        Image: workerName,
        Runtime: 'nvidia',
        NetworkMode: 'host',
        name: workerId,
        Env: [`worker_id=${workerId}`],
        Binds: [`${HOST_SHARED_DIR}:${CONTAINER_SHARED_DIR}`]
    };
    return docker.createContainer(params).then((container) => {
        return container.start();
    });
}

// Restart an exited worker.
async function restartWorker(workerId) {
    const container = docker.getContainer(workerId);

    const stats = await container.inspect();

    if (stats.State.Running) {
        return container.stop().then(() => container.start());
    } else {
        return container.start();
    }
}

// Remove a worker.
async function removeWorker(workerId) {
    const container = docker.getContainer(workerId);

    return container.remove({
        force: true,
    });
}

// Get the key of a worker to access the memory database.
function getWorkerKey(workerId) {
    return `res_mgr:worker:${workerId}`;
}

// Update the status of a worker.
async function updateWorkerStatus(workerId, status) {
    const workerKey = getWorkerKey(workerId);
    const workerInfo = JSON.stringify({
        status,
    });
    await mem_db_cli.setAsync(workerKey, workerInfo);
}

async function removeWorkerRecord(workerId) {
    const key = getWorkerKey(workerId);
    await mem_db_cli.delAsync(key);
}

// Helper function for replying to brain.
function replyBrain(reply) {
    const replyStr = JSON.stringify(reply);
    nats.request(CH_RES_TO_BRAIN, replyStr);
    console.log(`Reply to brain: ${replyStr}`);
}

// Helper function for replying response to brain.
function replyBrainResponse(originRequest, response) {
    const reply = merge({}, originRequest, {
        response,
    });
    replyBrain(reply);
}

// Helper function for replying error to brain.
function replyBrainError(originRequest, code) {
    const reply = merge({}, originRequest, {
        error: {
            code,
        },
    });
    replyBrain(originRequest, reply);
}

// The messaging handler from brain.
async function brainHandler(msg) {
    console.log(`Request from brain: ${msg}`);

    const request = JSON.parse(msg.replace(/'/g, '"'));
    // Parse the command.
    const { command } = request;

    switch (command) {
        case MESSAGING[CH_BRAIN_TO_RES]['CREATE_WORKER']: {
            const {
                workerName,
            } = request.params;

            // Check has the requested worker name or not.
            if (!hasWorkerName(workerName)) {
                replyBrainError(request, MESSAGING[CH_RES_TO_BRAIN]['NON_EXISTED_NAME']);
                return;
            }

            // Check has enough resource or not.
            if (!hasEnoughResource()) {
                replyBrainError(request, MESSAGING[CH_RES_TO_BRAIN]['OUT_OF_RESOURCE']);
                return;
            }

            // Reply to brain.
            const workerId = genWorkerId();
            replyBrainResponse(request, {
                workerId,
                status: WORKER_STATUS.CREATING,
            });

            try {
                // Update worker status as "CREATING"
                await updateWorkerStatus(workerId, WORKER_STATUS.CREATING);
                // Create a worker.
                await createWorker(workerId, workerName);
                // Update worker status as "RUNNING"
                await updateWorkerStatus(workerId, WORKER_STATUS.RUNNING);

                console.log(`Create worker (worker name=${workerName}, ID = ${workerId}) successfully`);
            } catch (e) {
                // TODO(JiaKuan Su): Error handling.
                console.error(e);
            }

            break;
        }

        case MESSAGING[CH_BRAIN_TO_RES]['RESTART_WORKERS']: {
            const { workerIds } = request.params;

            try {
                // TODO(JiaKuan Su): Check these workers exist.

                await Promise.all(map(workerIds, async (workerId) => {
                    // Restart the worker.
                    await restartWorker(workerId);
                    // Update worker status as "RUNNING"
                    await updateWorkerStatus(workerId, WORKER_STATUS.RUNNING);
                }));

                // TODO(JiaKuan Su): Send reply to brain.

                console.log(`Workers (IDs = ${workerIds}) has been restarted successfully`);
            } catch (e) {
                // TODO: Error handling.
                console.error(e)
            }

            break;
        }

        case MESSAGING[CH_BRAIN_TO_RES]['REMOVE_WORKER']: {
            const {
                workerId
            } = request.params;

            try {
                // Remove a worker.
                await removeWorker(workerId);
                // Remove worker status record in memory database
                await removeWorkerRecord(workerId);

                replyBrainResponse(request, {
                    status: WORKER_STATUS.REMOVED,
                });

                console.log(`Worker (ID = ${workerId}) has been removed successfully`);
            } catch (e) {
                // TODO: Error handling.
                console.error(e)
            }

            break;
        }

        default:
            replyBrainError(request, MESSAGING[CH_RES_TO_BRAIN]['NON_SUPPORTED_CMD']);
            console.error(`Unsupported command: ${command}`);
            break;
    }
}

nats.subscribe(CH_BRAIN_TO_RES, brainHandler);
