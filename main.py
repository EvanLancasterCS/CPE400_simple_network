from router import *

# Creates a 2 way connection between two routers
def createMutualConnection(routerA, routerB, bandwidth):
    routerA.createConnection(routerB, bandwidth, 0)
    routerB.createConnection(routerA, bandwidth, 0)

# Runs simulation for timeToRun steps
def runSimulationForTime(routers, timeToRun, time):
    for i in range(timeToRun):
        for j in range(len(routers)):
            routers[j].timeTick(time)
        time = time + 1

# uses the connection_info.ri file to create connections between the given
# array of routers
def createRouterConnectionsFromFile(routers):
    file = open("connection_info.ri", "r")
    file_content = file.read()

    content = file_content.split(",")
    
    for i in range(len(content)):
        content[i] = content[i].replace('\n', "")
        entry = content[i].split("|")

        idA = int(entry[0])
        idB = int(entry[1])
        bandwidth = int(entry[2])
        createMutualConnection(routers[idA], routers[idB], bandwidth)

# uses router_info.ri file to setup variables
def setupRouterVariablesFromFile(routers):
    file = open("router_info.ri", "r")
    file_content = file.read()

    content = file_content.split(",")
    
    for i in range(len(content)):
        content[i] = content[i].replace('\n', "")
        entry = content[i].split("|")
        maxQueueSize = int(entry[0])
        routers[i].maxQueueSize = maxQueueSize


if __name__ == "__main__":
    numRouters = 16
    routers = []
    for i in range(numRouters):
        routers.append(Router(i, numRouters))

    createRouterConnectionsFromFile(routers)
    setupRouterVariablesFromFile(routers)

    time = 0
    runSimulationForTime(routers, 50, time)

    # desynchronize router broadcasts
    for i in range(50):
        for j in range(len(routers)):
            if(random.random() > 0.5):
                routers[j].timeTick(time)
        time = time + 1

    # Trace packet demonstrating the path taken from router 0 to router 15
    tracePacket = Packet_META_Crafter.RoutingInfoTracePacket(routers[0], routers[15])
    routers[0].queuePacket(tracePacket, routers[0])

    runSimulationForTime(routers, 50, time)

    print("\nBEGIN: NETWORK BANDWIDTH TEST; 54 LARGE PACKETS SENT FROM r0, r1, r2, r13, r14, r15")
    # send lots of packets from the left side of the network to the right side of the network
    # to demonstrate the throughput of the network
    for i in range(3):
        for j in range(9):
            dataPacket = Packet(routers[i], routers[15], 10, "Test Packet", None, False)
            routers[i].queuePacket(dataPacket, routers[i])
    for i in range(3):
        for j in range(9):
            dataPacket = Packet(routers[15 - i], routers[4], 10, "Test Packet", None, False)
            routers[15 - i].queuePacket(dataPacket, routers[i])

    runSimulationForTime(routers, 50, time)

    print("\nBegin packet traces during high network use")
    tracePacket = Packet_META_Crafter.RoutingInfoTracePacket(routers[0], routers[15])
    routers[0].queuePacket(tracePacket, routers[0])

    tracePacket = Packet_META_Crafter.RoutingInfoTracePacket(routers[2], routers[15])
    routers[2].queuePacket(tracePacket, routers[2])

    tracePacket = Packet_META_Crafter.RoutingInfoTracePacket(routers[13], routers[4])
    routers[13].queuePacket(tracePacket, routers[13])

    runSimulationForTime(routers, 1000, time)



    runSimulationForTime(routers, 50, time)

    print("\nPacket trace 50 ticks after network cleared")
    tracePacket = Packet_META_Crafter.RoutingInfoTracePacket(routers[0], routers[15])
    routers[0].queuePacket(tracePacket, routers[0])

    runSimulationForTime(routers, 100, time)

    print("END: NETWORK BANDWIDTH TEST\n")


    
    #Demonstration of a router failure and subsequent network reaction
    routers[3].forceRouterFailure()

    print("\nForcing Router 3 to fail. Sending trace packet after 5 network ticks.")
    runSimulationForTime(routers, 5, time)

    tracePacket = Packet_META_Crafter.RoutingInfoTracePacket(routers[0], routers[15])
    routers[0].queuePacket(tracePacket, routers[2])
    runSimulationForTime(routers, 50, time)

    routers[6].forceRouterFailure()

    print("\nForcing Router 6 to fail. Sending trace packet after 5 network ticks.")
    runSimulationForTime(routers, 5, time)

    tracePacket = Packet_META_Crafter.RoutingInfoTracePacket(routers[0], routers[15])
    routers[0].queuePacket(tracePacket, routers[2])

    runSimulationForTime(routers, 50, time)
    