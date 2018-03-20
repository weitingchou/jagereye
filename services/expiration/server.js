const fs = require('fs');

const { CronJob } = require('cron');
const yaml = require('js-yaml');

const EventAgent = require('./EventAgent');

// Path to the event schema.
const EVENT_SCHEMA_PATH = '../../shared/event.json';
// Path to the config file.
const CONFIG_PATH = '../../shared/config.yml';
// Path to the shared directory.
const SHARED_DIR = `${process.env.HOME}/jagereye_shared`;

try {
    const config = yaml.safeLoad(fs.readFileSync(CONFIG_PATH))
    const {
        db_host: dbHost,
        expiration_days: expirationDays,
        max_event_records: maxEventRecords,
        repeat_period_mins: repeatPeriodMins,
    } = config.services.expiration.params;

    const job = new CronJob(`00 */${repeatPeriodMins} * * * *`, async () => {
        try {
            const eventAgent = new EventAgent(dbHost, EVENT_SCHEMA_PATH, SHARED_DIR);

            await eventAgent.deleteBefore(expirationDays);
            await eventAgent.deleteIfMoreThan(maxEventRecords);
        } catch (err) {
            console.error(err);
        }
    }, null, true);

    console.log(`Start a expiration cron job every ${repeatPeriodMins} minute(s)`);
} catch (e) {
    console.error(e)
}
