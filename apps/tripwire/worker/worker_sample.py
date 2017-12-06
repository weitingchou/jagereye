import proto 

worker = proto.Worker()


alert = worker.alert_to_brain 

def pipeline():
    i = 0
    while True:
        if i%1000000 == 0:
            alert("something happend "+str(i/1000000))
        i = i + 1

worker.register_pipeline(pipeline)

worker.start()
