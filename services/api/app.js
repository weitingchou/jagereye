const express = require('express')
const bodyParser = require('body-parser')

const cameras = require('./cameras')

const app = express()

app.use(bodyParser.json())
app.use(bodyParser.urlencoded({ extended: false }))

// Initialize API
app.use('/cameras', cameras)

// Logging errors
app.use((err, req, res, next) => {
    console.error(err.stack)
    next(err)
})

// Catch-all error handling
app.use((err, req, res, next) => {
    res.status(err.status).send(err.message)
})

module.exports = app
