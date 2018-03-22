const express = require('express')
const { checkSchema, validationResult } = require('express-validator/check')

const models = require('./database')
const { jwt, jwtOptions } = require('./passport')
const { createError } = require('./common')
const { ROLES } = require('./constants')

const router = express.Router()

function createValidationError(errors) {
    return createError(400, errors.array()[0]['msg'])
}

const userValidator = checkSchema({
    username: {
        exists: true,
        errorMessage: 'Username is required',
    },
    password: {
        exists: true,
        errorMessage: 'Password is required',
    },
})

const createUserValidator = checkSchema({
    role: {
        matches: {
            errorMessage: `Role should be "${ROLES.WRITER}" or "${ROLES.READER}"`,
            options: new RegExp(`\\b(${ROLES.WRITER}|${ROLES.READER})\\b`),
        },
    }
})

function createUser(req, res, next) {
    const errors = validationResult(req)

    if (!errors.isEmpty()) {
        return next(createValidationError(errors))
    }

    const { username, password, role } = req.body

    models.users.create({
        username,
        password,
        role,
    }, (err, result) => {
        if (err) {
            if (err.name === 'MongoError') {
                if (err.code === 11000) {
                    const dupKey = err.errmsg.slice(err.errmsg.lastIndexOf('dup key:') + 14, -3)

                    return next(createError(400, `Username exists: ${dupKey}`))
                }
            }

            return next(createError(500, null, err))
        }

        return res.status(201).send({id: result.id})
    })
}

function login(req, res, next) {
    const errors = validationResult(req)

    if (!errors.isEmpty()) {
        return next(createValidationError(errors))
    }

    const { username, password, role } = req.body

    models.users.findOne({
        username,
        password,
    }, (err, result) => {
        if (err) {
            return next(createError(500, null, err))
        }

        if (!result) {
            return next(createError(401, 'Incorrect username or password'))
        }

        const { id } = result
        const payload = { id }
        const token = jwt.sign(payload, jwtOptions.secretOrKey)

        return res.status(200).send({ id, token })
    })
}

router.post('/users', userValidator, createUserValidator, createUser)
router.post('/login', userValidator, login)

module.exports = router
