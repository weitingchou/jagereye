const WebSocket = require('ws')
const async = require('async')
const fs = require('fs')

var settings

var server
var wsServer


function notifying(event, callback) {
    if (typeof event !== 'string') {
        try {
            event = JSON.stringify(event)
        } catch (e) {
            return callback(e)
        }
    }
    async.each(wsServer.clients, (client, callback) => {
        client.send(event, (err) => {
            if (err) { return callback(err) }
            callback()
        })
    }, (err) => {
        if (err) { return callback(err) }
        callback()
    })
}

function notificationHandler(request, replyTo) {
    nats.publish(replyTo, 'OK')
    notifying(request, (err) => {
        if (err) {
            /* TODO: log error */
        }
    })
}

function init(_server, _settings) {
    server = _server
    settings = _settings
}

function start() {
    let path = settings.path || '/notification'
    wsServer = new WebSocket.Server({server: server, path: path})
    wsServer.on('connection', (ws) => {
        ws.isAlive = true
        ws.on('pong', () => {
            ws.isAlive = true
        })
        ws.on('close', () => {
            // TODO: log connection close
        })
        ws.on('error', (err) => {
            // TODO: log error
        })
    })
    wsServer.on('error', (err) => {
        // TODO: log error
    })
    nats.subscribe('ch_notification', notificationHandler)
    const heartbeatTimer = setInterval(function ping() {
        wsServer.clients.forEach((client) => {
            if (client.isAlive === false) {
                return client.terminate()
            }
            client.isAlive = false
            client.ping('', false, true)
        })
    }, settings.websocketKeepAliveTime || 10000)
}

function stop() {
    if (wsServer) {
        wsServer.close()
        wsServer = null
    }
}


module.exports = {
    init: init,
    start: start,
    stop: stop
}
