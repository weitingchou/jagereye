const express = require('express')
const { checkSchema } = require('express-validator/check')

const models = require('./database')
const { createError, validate, isValidId } = require('./common')
const { jwt, jwtOptions } = require('./auth/passport')
const { routesWithAuth } = require('./auth')
const { ROLES } = require('./constants')

/*
 * Projections
 */
const getUserProjection = {
    'id': 1,
    'username': 1,
    'role': 1,
}

const router = express.Router()

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

async function getAllUsers(req, res, next) {
    try {
        const list = await models.users.find({}, getUserProjection)

        return res.send(list)
    } catch (err) {
        return next(createError(500, null, err))
    }
}

async function createUser(req, res, next) {
    const { username, password, role } = req.body

    try {
        const result = await models.users.create({
            username,
            password,
            role,
        })

        return res.status(201).send({ id: result.id })
    } catch (err) {
        if (err.name === 'MongoError') {
            if (err.code === 11000) {
                const dupKey = err.errmsg.slice(err.errmsg.lastIndexOf('dup key:') + 14, -3)

                return next(createError(400, `Username exists: ${dupKey}`))
            }
        }

        return next(createError(500, null, err))
    }
}

async function getUser(req, res, next) {
    const { id: targetId } = req.params
    const { id: requesterId, role: requesterRole } = req.user

    if (!isValidId(targetId)) {
        return next(createError(400, 'Unvalid ID'))
    }

    // TODO(JiaKuan Su): The rule to get user should be discussed.
    // Non-admin user can only get its information.
    if (requesterRole !== ROLES.ADMIN && requesterId !== targetId) {
        return next(createError(400, 'Request non-self user'))
    }

    try {
        const result = await models.users.findById(targetId, getUserProjection)

        if (!result) {
            return next(createError(404, 'User not existed'))
        }

        res.send(result)
    } catch (err) {
        return next(createError(500, null, err))
    }
}

async function login(req, res, next) {
    const { username, password, role } = req.body

    try {
        const result = await models.users.findOne({
            username,
            password,
        })

        if (!result) {
            return next(createError(401, 'Incorrect username or password'))
        }

        const { id } = result
        const payload = { id }
        const token = jwt.sign(payload, jwtOptions.secretOrKey)

        return res.status(200).send({ id, token })
    } catch (err) {
        return next(createError(500, null, err))
    }
}

/*
 * Routing Table
 */
routesWithAuth(
    router,
    ['get', '/users', getAllUsers],
    ['post', '/users', userValidator, createUserValidator, validate, createUser],
)
routesWithAuth(
    router,
    ['get', '/user/:id', getUser],
)
router.post('/login', userValidator, validate, login)

module.exports = router
