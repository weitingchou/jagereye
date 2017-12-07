const mongoose = require('mongoose')
const Schema = mongoose.Schema
const fs = require('fs')

// Use bluebird for Mongoose
mongoose.Promise = require('bluebird')

const conn = mongoose.createConnection('mongodb://localhost:27017/jager_test')

schema = JSON.parse(fs.readFileSync('../database/schema.json', 'utf8'))

var Models = {}

Object.keys(schema).forEach((modelName) => {
    Models[modelName] = conn.model(modelName, new Schema(schema[modelName]))
})

module.exports = Models
