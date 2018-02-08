const fs = require('fs');
const path = require('path');

const concat = require('lodash/concat');
const find = require('lodash/find');
const forEach = require('lodash/forEach');
const includes = require('lodash/includes');
const isString = require('lodash/isString');
const mongoose = require('mongoose');
const Promise = require('bluebird');
const reduce = require('lodash/reduce');

const { forEachAsync } = require('./utils');

const deleteFile = Promise.promisify(fs.unlink);

mongoose.Promise = require('bluebird');

const { Schema } = mongoose;

class EventAgent {
    constructor(dbHost, schemaPath, sharedDir) {
        this.dbHost = dbHost;
        this.schemaPath = schemaPath;
        this.sharedDir = sharedDir

        this.conn = mongoose.createConnection(dbHost);
        this.baseModel = this.createBaseModel();
        this.appModels = []
    }

    // Create model for base events.
    createBaseModel() {
        const schemaJSON = JSON.parse(fs.readFileSync(this.schemaPath, 'utf8'))
        const { properties, required } = schemaJSON;
        const schema = properties;

        forEach(properties, (value, key) => {
            if (includes(required, key)) {
                schema[key].required = true;
            }
        });

        return this.createModel('base', 'events', schema);
    }

    // Create model for application contents.
    createAppModel(appName) {
        return this.createModel(appName, `events_${appName}`, {});
    }

    // Generic function for creating a model.
    createModel(name, collection, schema) {
        const schemaObj = new Schema(schema, { collection });
        const model = this.conn.model(collection, schemaObj);

        return {
            name,
            model
        };
    }

    // Delete events before a given day(s) ago.
    async deleteBefore(days) {
        console.log(`== Try to delete data before ${days} day(s) ago ==`);

        // Convert days into seconds.
        const seconds = days * 24 * 60 * 60;
        // Calculate the maximum timestamp (in seconds) that allows events to
        // live.
        const maxTimestamp = Date.now() / 1000 - seconds;

        await this.delete([{
            $match: {
                timestamp: {
                    $lte: maxTimestamp,
                },
            },
        }]);

        console.log(`== Success to delete data before ${days} day(s) ago ==`);
    }

    // Delete events if the number of stored records is more than a given
    // maximum number. If exceeds, the oldest records will be deleted first.
    // TODO(JiaKuan SU): We can also consider to calculate the storage space
    // directly.
    async deleteIfMoreThan(maxNum) {
        console.log(`== Try to delete data if the stored records is more than ${maxNum} ==`);

        const count = await this.baseModel.model.count();

        if (count > maxNum) {
            await this.delete([{
                $sort: {
                    timestap: -1
                },
            }, {
                $limit: count - maxNum
            }]);
        }

        console.log(`== Success to delete data if the stored records is more than ${maxNum} ==`);
    }

    // Generic function for events deletion.
    async delete(filters) {
        const aggregations = concat(filters, {
            $group: {
                _id: '$appName',
                eventIds: {
                    $push: '$_id',
                },
                contentIds: {
                    $push: '$content',
                },
            },
        });

        // Find all matched base events and group them by application names.
        const eventGroups = await this.baseModel.model.aggregate(aggregations);

        // Handle for each application group.
        await forEachAsync(eventGroups, async (eventGroup) => {
            // Find the model belongs to the application.
            const appName = eventGroup._id;
            let appModel = find(this.appModels, {
                name: appName,
            })

            // If If the application model does not exist, create one and
            // put that into the application models pool.
            if (!appModel) {
                appModel = this.createAppModel(appName);
                this.appModels.push(appModel);
            }

            // Find out the contents in the application group.
            const { contentIds } = eventGroup;
            const query = {
                _id: {
                    $in: contentIds,
                },
            }
            const contents = await appModel.model.find(query);

            // Delete all files whose paths are stored in contents.
            await forEachAsync(contents, async (content) => {
                await forEachAsync(content.toObject(), async (value) => {
                    if (isString(value)) {
                        const absPath = path.join(this.sharedDir, value);
                        const existed = fs.existsSync(absPath);

                        if (existed) {
                            await deleteFile(absPath);

                            console.log(`Delete file: ${absPath}`);
                        }
                    }
                });
            });

            // Remove the records of contents in database.
            await appModel.model.remove(query);

            console.log(`Delete ${contentIds.length} content records for ${appName}: ${contentIds}`);
        });

        // Get all events IDs.
        const allEventIds = reduce(eventGroups, (result, value) => (
            concat(result, value.eventIds)
        ), []);

        // Delete all events.
        await this.baseModel.model.remove({
            _id: {
                $in: allEventIds,
            },
        });

        if (allEventIds.length > 0) {
            console.log(`Delete ${allEventIds.length} event records: ${allEventIds}`);
        }
    }
}

module.exports = EventAgent;
