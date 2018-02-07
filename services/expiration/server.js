const { CronJob } = require('cron');

const EventAgent = require('./EventAgent');

// Database host URL.
const DB_HOST = 'mongodb://localhost:27017/jager_test';
// Path to the event schema.
const EVENT_SCHEMA_PATH = '../../shared/event.json';
// Path to the shared directory.
const SHARED_DIR = `${process.env.HOME}/jagereye_shared`;
// Expiration period in days.
const EXPIRATION_DAYS = 30;
// Repeat period of expiration function (in minutes).
const REPEAT_PERIOD_MINS = 1;

const job = new CronJob(`00 */${REPEAT_PERIOD_MINS} * * * *`, async () => {
    try {
        const eventAgent = new EventAgent(DB_HOST, EVENT_SCHEMA_PATH, SHARED_DIR);

        await eventAgent.deleteBefore(EXPIRATION_DAYS);
    } catch (err) {
        console.error(err);
    }
}, null, true);

console.log(`Start a expiration cron job every ${REPEAT_PERIOD_MINS} minute(s)`);
