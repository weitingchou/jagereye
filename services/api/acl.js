const acl = require('express-acl')

const { createError } = require('./common')

acl.config({
    baseUrl: 'api/v1',
    decodedObjectName: 'user',
    filename: 'acl.json',
})

module.exports = {
    authorize: acl.authorize,
}
