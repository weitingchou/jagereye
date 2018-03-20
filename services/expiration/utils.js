const map = require('lodash/map');
const Promise = require('bluebird');

function forEachAsync(collection, iteratee) {
    return Promise.all(map(collection, iteratee));
}

module.exports = {
    forEachAsync
};
