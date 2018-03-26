const express = require('express')
const jwt = require('jsonwebtoken')
const passport = require('passport')
const passportJWT = require("passport-jwt")

const models = require('../database')
const { createError } = require('../common')

const router = express.Router()

// TODO(JiaKuan Su): Load secret from config file.
const JWT_SECRET = 'jagereye'

/*
 * Projections
 */
const getUserProjection = {
    id: 1,
    role: 1,
}

const jwtOptions = {
    jwtFromRequest: passportJWT.ExtractJwt.fromAuthHeaderAsBearerToken(),
    secretOrKey: JWT_SECRET,
}

passport.use(new passportJWT.Strategy(jwtOptions, (payload, done) => {
    return models.users.findById(payload.id, getUserProjection, (err, user) => {
        if (err) {
            return done(createError(500, null, err), false)
        }

        if (!user) {
            return done(createError(401, 'Unauthenticated'), false)
        }

        return done(null, user)
    })
}))

const authenticate = passport.authenticate('jwt', { session: false })

module.exports = {
    authenticate,
    jwt,
    jwtOptions,
}
