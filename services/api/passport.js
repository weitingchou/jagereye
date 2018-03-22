const express = require('express')
const jwt = require('jsonwebtoken')
const passport = require('passport')
const passportJWT = require("passport-jwt")

const models = require('./database')

const router = express.Router()

// TODO(JiaKuan Su): Load secret from config file.
const JWT_SECRET = 'jagereye'

const jwtOptions = {
    jwtFromRequest: passportJWT.ExtractJwt.fromAuthHeaderAsBearerToken(),
    secretOrKey: JWT_SECRET,
}

passport.use(new passportJWT.Strategy(jwtOptions, (jwtPyaload, cb) => {
    return models.users.findOneById(jwtPayload.id, (err, user) => {
        if (err) {
            return cb(err)
        }

        return cb(null, user)
    })
}))

const authenticate = passport.authenticate('jwt', { session: false })

module.exports = {
    jwt,
    jwtOptions,
    authenticate,
}
