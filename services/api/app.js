const express = require('express')
const bodyParser = require('body-parser')
const expressValidator = require('express-validator')

const analyzers = require('./analyzers')

const app = express()

app.use(bodyParser.json())
app.use(bodyParser.urlencoded({ extended: false }))
app.use(expressValidator())

// Initialize API
analyzers.addTo(app)

// Logging errors
app.use((err, req, res, next) => {
    console.error(err.stack)
    next(err)
})

// Catch-all error handling
app.use((err, req, res, next) => {
    const error = {
        code: err.code,
        message: err.message
    }
    res.status(err.status).send(error)
})

module.exports = app
