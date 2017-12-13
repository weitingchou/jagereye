const http = require('http')
const NATS = require('nats')

const app = require('./app')
const notification = require('./notification')


// Initialize NATS
// const servers = ['nats://192.168.1.2:4222']
const servers = ['nats://localhost:4222']
global.nats = NATS.connect({
    'maxReconnectAttempts': -1,
    'reconnectTimeWait': 250,
    'servers': servers
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

notification.init(server, {})
notification.start()

const port = 5000
server.listen(port, (error) => {
    if (error) {
        console.error(error)
    } else {
        console.info(`==> Listening on port ${port}`)
    }
})
