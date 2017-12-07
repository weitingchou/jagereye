const http = require('http')
const NATS = require('nats')
const app = require('./app')


// Initialize NATS
global.nats = NATS.connect({
    'maxReconnectAttempts': -1,
    'reconnectTimeWait': 250
})
nats.on('error', (err) => {
    console.error(err)
})
nats.on('connect', (nc) => {
    console.log('connected')
})
nats.on('disconnect', () => {
    console.log('disconnected')
})
nats.on('reconnecting', () => {
    console.log('reconnecting')
})
nats.on('close', () => {
    console.log('connection closed')
})

const server = http.createServer(app)

const port = 5000
server.listen(port, (error) => {
    if (error) {
        console.error(error)
    } else {
        console.info(`==> Listening on port ${port}`)
    }
})
