const acl = require('express-acl')

acl.config({
    baseUrl: 'api/v1',
    decodedObjectName: 'user',
    path: 'auth',
    filename: 'acl.json',
})

module.exports = {
    authorize: acl.authorize,
}
