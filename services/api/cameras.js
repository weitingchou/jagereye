const router = require('express').Router()
const httpError = require('http-errors')
const models = require('./database')
const NATS = require('nats')
const fs = require('fs')

messaging = JSON.parse(fs.readFileSync('../messaging.json', 'utf8'))


function createError(status, message, origErrObj) {
    let error = new Error()
    error.status = status
    if (message) {
        error.message = message
    } else {
        error.message = httpError(status)
    }

    if (origErrObj) {
        if (origErrObj.kind === 'ObjectId') {
            error.status = 400
            error.message = 'Invalid ObjectId format'
        }
        error.stack = origErrObj.stack
    }

    return error
}

router.post('/', (req, res, next) => {
    let inst = new models['cameras']({
        device_name: req.body['device_name'],
        streaming_protocol: req.body['streaming_protocol'],
        host: req.body['host'],
        port: req.body['port']
    })
    inst.save((err, saved) => {
        if (err) {
            return next(createError(500, null, err))
        }
        res.send({id: saved.id})
    })
})

router.get('/:id', (req, res, next) => {
    models['cameras'].findById(req.params['id'], (err, inst) => {
        if (err) {
            return next(createError(500, null, err))
        }
        if (inst === null) {
            return next(createError(404))
        }
        res.send({
            device_name: inst['device_name'],
            streaming_protocol: inst['streaming_protocol'],
            host: inst['host'],
            port: inst['port'],
            path: inst['path'],
            enabled: inst['enabled']
        })
    })
})

router.delete('/:id', (req, res, next) => {
    models['cameras'].findByIdAndRemove(req.params.id, (err) => {
        if (err) {
            return next(createError(500, null, err))
        }
        res.send({message: 'succeed'})
    })
})

router.post('/:id/application', (req, res, next) => {
    models['cameras'].findById(req.params['id'], (err, inst) => {
        if (err) {
            return next(createError(500, null, err))
        }
        if (inst === null) {
            return next(createError(404))
        }

        let request = JSON.stringify({
            command: messaging['ch_api_brain']['START_APPLICATION'],
            params: {
                camera: {
                    id: req.params['id'],
                    protocol: inst['streaming_protocol'],
                    host: inst['host'],
                    port: inst['port'],
                    path: inst['path']
                },
                application: {
                    name: req.body['name'],
                    params: req.body['params']
                }
            }
        })
        nats.requestOne('ch_api_brain', request, {}, 1000, (reply) => {
            if (reply.code && reply.code === NATS.REQ_TIMEOUT) {
                return next(createError(500))
            }
            if (reply !== 'OK') {
                return next(createError(500, reply))
            }
            if (inst['enabled'] === false) {
                inst['enabled'] = true
                inst.save((err) => {
                    if (err) {
                        return next(createError(500, null, err))
                    }
                    res.send(reply)
                })
            } else {
                res.send(reply)
            }
        })
    })
})

router.get('/:id/application', (req, res, next) => {
    let request = JSON.stringify({
        command: messaging['ch_api_brain']['REQ_APPLICATION_STATUS'],
        params: {
            camera: {
                id: req.params['id']
            }
        }
    })
    nats.requestOne('ch_api_brain', request, {}, 1000, (reply) => {
        if (reply.code && reply.code === NATS.REQ_TIMEOUT) {
            return next(createError(500))
        }
        res.send(reply)
    })
})

router.delete('/:id/application', (req, res, next) => {
    let request = JSON.stringify({
        command: messaging['ch_api_brain']['STOP_APPLICATION'],
        params: {
            camera: {
                id: req.params['id']
            }
        }
    })
    nats.requestOne('ch_api_brain', request, {}, 1000, (reply) => {
        if (reply.code && reply.code === NATS.REQ_TIMEOUT) {
            return next(createError(500))
        }
        if (reply !== 'OK') {
            return next(createError(500, reply))
        }
        models['cameras'].findByIdAndUpdate(req.params['id'], {
            enabled: false
        }, (err) => {
            if (err) {
                return next(createError(500, null, err))
            }
            res.send(reply)
        })
    })
})

module.exports = router
