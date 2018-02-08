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
// The maximum allowance of event records.
// The number "400,000" is for 1TB storage space, it assumes each event
// contains about 2.2MB, including the database record, a 10-seconds video,
// a thumbnail and a metadata json file.
const MAX_EVENT_RECORDS = 400000;
// Repeat period of expiration function (in minutes).
const REPEAT_PERIOD_MINS = 1;

const job = new CronJob(`00 */${REPEAT_PERIOD_MINS} * * * *`, async () => {
    try {
        const eventAgent = new EventAgent(DB_HOST, EVENT_SCHEMA_PATH, SHARED_DIR);

        await eventAgent.deleteBefore(EXPIRATION_DAYS);
        await eventAgent.deleteIfMoreThan(MAX_EVENT_RECORDS);
    } catch (err) {
        console.error(err);
    }
}, null, true);

console.log(`Start a expiration cron job every ${REPEAT_PERIOD_MINS} minute(s)`);
