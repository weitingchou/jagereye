const acl = require('express-acl')

acl.config({
    baseUrl: 'api/v1',
    decodedObjectName: 'user',
    path: 'auth',
    filename: 'acl.json',
})

module.exports = {
    // FIXME(JiaKuan Su):
    // Currently, the authorize middleware can not be integrated with
    // "createError()", so the authorization error will not be shown in API
    // service. Please fix it in the future.
    authorize: acl.authorize,
}
