const express = require('express')
const { body, validationResult } = require('express-validator/check')
const httpError = require('http-errors')
const models = require('./database')
const NATS = require('nats')
const fs = require('fs')

const analyzersRouter = express.Router()
const analyzerRouter = express.Router()

const msg = JSON.parse(fs.readFileSync('../messaging.json', 'utf8'))
const MAX_ENABLED_ANALYZERS = 16
const NUM_OF_BRAINS = 1
const DEFAULT_REQUEST_TIMEOUT = 3000
const CH_API_BRAIN = 'ch_api_brain'

/*
 * Projections
 */
const getConfProjection = {
    '_id': 0,
    'name': 1,
    'type': 1,
    'enabled': 1,
    'source': 1,
    'pipelines': 1
}
const getConfSourceProjection = {
    '_id': 0,
    'name': 0,
    'type': 0,
    'enabled': 0,
    'source': 1,
    'pipelines': 0
}
const getConfPipelineProjection = {
    '_id': 0,
    'name': 0,
    'type': 0,
    'enabled': 0,
    'source': 0,
    'pipelines': 1
}

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

function postReqValidator(req, res, next) {
    const errors = validationResult(req)
    if (!errors.isEmpty()) {
        return next(createError(400, null))
    }

    // TODO: Should find a way to enforce maximum enabled analyzers
    //       at MongoDB writing
    models['analyzers'].count({'enabled': true}, (err, count) => {
        if (err) { return next(createError(500, null, err)) }
        if (count >= MAX_ENABLED_ANALYZERS) {
            return next(createError(400, 'Exceeded maximum number of analyzers allow to be enabled'))
        }
        next()
    })
}

function requestBrain(request, timeout, callback) {
    let reqTimeout = timeout
    let cb = callback
    let ignore = false
    let count = 0

    if (typeof reqTimeout === 'function') {
        reqTimeout = DEFAULT_REQUEST_TIMEOUT
        cb = timeout
    }

    const timer = setTimeout(() => {
        ignore = true
        cb({ code: NATS.REQ_TIMEOUT })
    }, reqTimeout)

    function closeResponse() {
        ignore = true
        clearTimeout(timer)
    }

    nats.request(CH_API_BRAIN, request, {'max': NUM_OF_BRAINS}, (reply) => {
        if (!ignore) {
            count += 1
            let isLastReply = count === NUM_OF_BRAINS ? true : false
            if (isLastReply) { clearTimeout(timer) }
            try {
                const replyJSON = JSON.parse(reply)
                cb(replyJSON, isLastReply, closeResponse)
            } catch (e) {
                cb({ error: { message: e } }, null ,closeResponse)
            }
        }
    })
}

function getAllAnalyzerConfig(req, res, next) {
    const searchQuery = req.query['search']
    let query = {}
    switch (searchQuery) {
        case 'enabled':
            query['enabled'] = true
            break
        default:
            return next(createError(400, `Invalid search query: ${searchQuery}`))
    }
    models['analyzers'].find(query, getConfProjection, (err, list) => {
        if (err) { return next(createError(500, null, err)) }
        res.send(list)
    })
}

function createAnalyzerConfig(req, res, next) {
    /* Validate request */
    req.checkBody('name', 'Analyzer name is required').notEmpty()
    const errors = req.validationErrors()
    if (errors) {
        return next(createError(400, errors.array()['msg']))
    }

    let config = { name: req.body['name'] }
    if (req.body['type']) { config['type'] = req.body['type'] }
    if (req.body['enabled']) { config['enabled'] = req.body['enabled'] }
    if (req.body['source']) { config['source'] = req.body['source'] }
    if (req.body['pipelines']) { config['pipelines'] = req.body['pipelines'] }
    const analyzer = new models['analyzers'](config)
    analyzer.save((err, saved) => {
        if (err) {
            if (err.name === 'ValidationError') {
                return next(createError(400, null, err))
            }
            else if (err.name === 'MongoError') {
                if (err.code === 11000) {
                    let dupKey = err.errmsg.slice(err.errmsg.lastIndexOf('dup key:') + 14, -3)
                    return next(createError(400, `Duplicate key error: ${dupKey}`, err))
                }
            }
            return next(createError(500, null, err))
        }
        res.status(201).send({id: saved.id})
    })
}

function deleteAllAnalyzers(req, res, next) {

}

function getAnalyzerConfig(req, res, next) {
    const id = req.params['id']
    models['analyzers'].findById(id, getConfProjection, (err, result) => {
        if (err) {
            return next(createError(500, null, err))
        }
        if (result === null) {
            return next(createError(404))
        }
        res.send(result)
    })
}

function deleteAnalyzer(req, res, next) {
    const id = req.params['id']
    const request = JSON.stringify({
        command: msg['ch_api_brain']['STOP_ANALYZER'],
        params: { id }
    })
    requestBrain(request, (reply, isLastReply, closeResponse) => {
        if (reply['error']) {
            closeResponse()
            return next(createError(500, reply['error']['message']))
        }
        if (reply['result']) {
            closeResponse()
            models['analyzers'].findByIdAndRemove(id, (err) => {
                if (err) {
                    return next(createError(500, null, err))
                }
                res.status(204).send()
            })
        }
        else if (reply['code']) {
            if (reply['code'] === NATS.REQ_TIMEOUT) {
                let error = new Error(`Timeout Error: Request: deleting runtime instance of analyzer "${id}"`)
                return next(createError(500, null, error))
            }
            if (reply['code'] === msg['ch_api_brain_reply']['NOT_FOUND']) {
                // Ignore if it's not the last reply
                if (isLastReply) {
                    closeResponse()
                    next(createError(404, `Runtime instance of analyzer "${id}" was not found`))
                }
            }
        }
    })
}

function updateAnalyzerConfig(req, res, next) {

}

function getAnalyzerSourceConfig(req, res, next) {
    const id = req.params['id']
    models['analyzers'].findById(id, getConfSourceProjection, (err, result) => {
        if (err) {
            return next(createError(500, null, err))
        }
        if (result === null) {
            return next(createError(404))
        }
        res.send(result)
    })
}

function updateAnalyzerSourceConfig(req, res, next) {

}

function getAnalyzerPipelineConfig(req, res, next) {
    const id = req.params['id']
    models['analyzers'].findById(id, getConfSourceProjection, (err, result) => {
        if (err) {
            return next(createError(500, null, err))
        }
        if (result === null) {
            return next(createError(404))
        }
        res.send(result)
    })
}

function updateAnalyzerPipelineConfig(req, res, next) {

}

function getAnalyzerRuntime(req, res, next) {
    const id = req.params['id']
    const request = JSON.stringify({
        command: msg['ch_api_brain']['REQ_ANALYZER_STATUS'],
        params: { id }
    })
    requestBrain(request, (reply, isLastReply, closeResponse) => {
        if (reply['error']) {
            closeResponse()
            return next(createError(500, reply['error']['message']))
        }
        if (reply['result']) {
            closeResponse()
            return res.send(reply['result'])
        }
        if (reply['code']) {
            if (reply['code'] === NATS.REQ_TIMEOUT) {
                let error = new Error(`Timeout Error: Request: getting runtime status of analyzer "${id}"`)
                return next(createError(500, null, error))
            }
            if (reply['code'] === msg['ch_api_brain_reply']['NOT_FOUND']) {
                // Ignore if it's not the last reply
                if (isLastReply) {
                    closeResponse()
                    next(createError(404, `Runtime instance of analyzer "${id}" was not found`))
                }
            }
        }
    })
}

function createAnalyzerRuntime(req, res, next) {
    const id = req.params['id']
    models['analyzers'].findById(id, (err, analyzer) => {
        if (err) {
            return next(createError(500, null, err))
        }
        if (analyzer === null) {
            return next(createError(404))
        }

        if (!analyzer['enabled']) {
            return next(createError(400, 'Cannot create runtime instance for unenabled analyzer'))
        }

        const type = analyzer['type']
        const source = analyzer['source']
        const pipelines = analyzer['pipelines']

        // Validate request
        if (!type) {
            return next(createError(400, 'Analyzer type is required'))
        }
        if (!source) {
            return next(createError(400, 'Analyzer source is required'))
        }
        if (!pipelines) {
            return next(createError(400, 'Analyzer pipeline is required'))
        }

        const request = JSON.stringify({
            command: msg['ch_api_brain']['START_ANALYZER'],
            params: { id, type, source, pipelines }
        })
        requestBrain(request, (reply, isLastReply, closeResponse) => {
            if (reply['code'] && reply['code'] === NATS.REQ_TIMEOUT) {
                let error = new Error(`Timeout Error: Request: creating runtime instance of analyzer "${id}"`)
                return next(createError(500, null, error))
            }
            if (reply['error']) {
                closeResponse()
                return next(createError(500, reply['error']['message']))
            }
            if (reply['result']) {
                closeResponse()
                return res.status(201).send(reply['result'])
            }
        })
    })
}

function updateAnalyzerRuntime(req, res, next) {

}

function deleteAnalyzerRuntime(req, res, next) {
    const id = req.params['id']
    const request = JSON.stringify({
        command: msg['ch_api_brain']['STOP_ANALYZER'],
        params: { id }
    })
    requestBrain(request, (reply, isLastReply, closeResponse) => {
        if (reply['error']) {
            closeResponse()
            return next(createError(500, reply['error']['message']))
        }
        if (reply['result']) {
            closeResponse()
            return res.status(204).send()
        }
        if (reply['code']) {
            if (reply['code'] === NATS.REQ_TIMEOUT) {
                let error = new Error(`Timeout Error: Request: deleting runtime instance of analyzer "${id}"`)
                return next(createError(500, null, error))
            }
            if (reply['code'] === msg['ch_api_brain_reply']['NOT_FOUND']) {
                // Ignore if it's not the last reply
                if (isLastReply) {
                    closeResponse()
                    next(createError(404, `Runtime instance of analyzer "${id}" was not found`))
                }
            }
        }
    })
}

/*
 * Routing Table
 */
analyzersRouter.get('/', getAllAnalyzerConfig)
analyzersRouter.post('/', postReqValidator,  createAnalyzerConfig)
analyzersRouter.delete('/', deleteAllAnalyzers)

analyzerRouter.get('/:id', getAnalyzerConfig)
analyzerRouter.patch('/:id', updateAnalyzerConfig)
analyzerRouter.delete('/:id', deleteAnalyzer)
analyzerRouter.get('/:id/source', getAnalyzerSourceConfig)
analyzerRouter.patch('/:id/source', updateAnalyzerSourceConfig)
analyzerRouter.get('/:id/pipelines', getAnalyzerPipelineConfig)
analyzerRouter.patch('/:id/pipelines', updateAnalyzerPipelineConfig)
analyzerRouter.get('/:id/runtime', getAnalyzerRuntime)
analyzerRouter.post('/:id/runtime', createAnalyzerRuntime)
analyzerRouter.patch('/:id/runtime', updateAnalyzerRuntime)
analyzerRouter.delete('/:id/runtime', deleteAnalyzerRuntime)

function addTo(app) {
    app.use('/analyzers', analyzersRouter)
    app.use('/analyzer', analyzerRouter)
}

module.exports = {
    addTo: addTo
}
