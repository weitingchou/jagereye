const mongoose = require('mongoose')
const Schema = mongoose.Schema
const fs = require('fs')
const JSONPath = require('JSONPath')

const schemaUrl = '../database/schema.json'

// Use bluebird for Mongoose
mongoose.Promise = require('bluebird')

const conn = mongoose.createConnection('mongodb://localhost:27017/jager_test')

function importSchema(schemaUrl) {
    const schemaJSON = JSON.parse(fs.readFileSync(schemaUrl, 'utf8'))
    const mainDocSchemaList = Object.keys(schemaJSON).filter((key) => {
        return !key.startsWith('subdoc_')
    })
    const subDocSchemaList = Object.keys(schemaJSON).filter((key) => {
        return key.startsWith('subdoc_')
    })
    let mainDocSchemaObj = {}
    let subDocSchemaObj = {}

    // Import subdocument schema first
    subDocSchemaList.forEach((item) => {
        // Validate schema
        let result = JSONPath({json: schemaJSON[item], path: '$..*@string()'}).filter((value) => {
            return value.startsWith('SUBDOC_')
        })
        if (result && result.length > 0) {
            throw new Error('Subdocument of subdocument is not allow')
        }

        // Create subdocument object
        subDocSchemaObj[item] = new Schema(schemaJSON[item])
    })

    // For each main document schema, replace the subdocument placeholder
    // with real subdocument object and create the schema object
    mainDocSchemaList.forEach((item) => {
        let propertyList = JSONPath({json: schemaJSON[item], path: '$..*@string()', resultType: 'all'})
        let subDocPropertyList = propertyList.filter((property) => {
            return property.value.startsWith('SUBDOC_')
        })
        subDocPropertyList.forEach((property) => {
            // Find matching subdocument schema object
            let match = Object.keys(subDocSchemaObj).find((obj) => {
                return obj.toUpperCase() === property.value
            })
            if (!match) {
                throw new Error(`Unable to find definition for subdocument placeholder "${property.value}" in main document schema "${item}"`)
            }

            let pathArray = JSONPath.toPathArray(property.path)
            let parentProperty = pathArray.slice(1, -1).reduce((accu, curr) => {
                return accu ? accu[curr] : null
            }, schemaJSON[item])
            parentProperty[pathArray.pop()] = subDocSchemaObj[match]
        })
        mainDocSchemaObj[item] = new Schema(schemaJSON[item])
    })
    return mainDocSchemaObj
}


const schemaObj = importSchema(schemaUrl)

let Models = {}
Object.keys(schemaObj).forEach((objName) => {
    Models[objName] = conn.model(objName, schemaObj[objName])
})

module.exports = Models
