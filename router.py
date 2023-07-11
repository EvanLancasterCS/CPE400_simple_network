import random
import math

ROUTER_MAX_PQUEUE_SIZE = 1
ROUTER_PROC_DELAY = 1
ROUTER_BROADCAST_FREQUENCY = 10
ROUTER_INITIAL_BROADCAST_FREQUENCY = 1
ROUTER_INTIALIZATION_TIME = 10
ROUTER_THROUGHPUT_DECAY = 0.2
ROUTER_THROUGHPUT_DECAY_FREQUENCY = 10

# Router class representing a real router with connections, routing table, queueing, 
# processing, etc.
class Router:
    def __init__(self, routerID, numRouters):
        self.routerID = routerID
        self.connections = [] # connection objects
        self.routingTable = [] # [destID, cost, nextRouterObj]
        self.queuedPackets = []
        self.queueSize = 0
        self.maxQueueSize = ROUTER_MAX_PQUEUE_SIZE
        self.numRouters = numRouters
        self.timeSinceBroadcast = 0

        self.currentPacket = None
        self.currentConnectionID = None
        self.currentPacketProg = 0

        # setup routing table defaults
        # [id, distance, nextRouter]
        for i in range(numRouters):
            if i == self.routerID:
                self.routingTable.append([i, 0, None])
                continue

            self.routingTable.append([i, 99999999, None])

    # go through our routing table and check if we are using this connection for anything. 
    # if we are, update the costs relative to the old cost so that we can optimize the
    # connection potentially in the future
    def updateConnectionRouting(self, connection, oldConnectionCost):
        connectionRouterID = connection.other.routerID
        difference = connection.cost - oldConnectionCost
        for i in range(len(self.routingTable)):
            entry = self.routingTable[i]
            
            if(entry[2] != None and entry[2].routerID == connectionRouterID):
                # update the cost based on the difference
                entry[1] += difference
    
    # should be ran every time we send out information to return to our
    # normal throughput after failure
    def checkConnectionThrottles(self):
        for i in range(len(self.connections)):
            connection = self.connections[i]
            cID = self.connections.index(connection)
            if(connection.throttlePercent != 1):
                if(connection.throttlePercent >= 0.95):
                    self.updateConnectionThrottle(cID, 1)
                else:
                    connection.throttlePercent += (1 - connection.throttlePercent) * ROUTER_THROUGHPUT_DECAY
                    #print(connection.throttlePercent)

    # update a connections throttle percentage
    def updateConnectionThrottle(self, cID, percentage):
        oldCost = self.connections[cID].cost
        self.connections[cID].updateThrottlePercent(percentage)
        self.updateConnectionRouting(self.connections[cID], oldCost)

    # update a connections possible throughput percentage
    def updateConnectionThroughput(self, cID, percentage):
        oldCost = self.connections[cID].cost
        self.connections[cID].updateThroughputPercent(percentage)
        self.updateConnectionRouting(self.connections[cID], oldCost)

    # forces all of the connections out of this router to fail, or be very slow
    def forceRouterFailure(self):
        for i in range(len(self.connections)):
            self.updateConnectionThroughput(i, 0.01)
    
    # sets the router to full throughput
    def forceFullThroughput(self):
        for i in range(len(self.connections)):
            self.updateConnectionThroughput(i, 1)
        

    # deconstructs packet's meta information and handles different types
    def processPacketMeta(self, packet):
        meta = packet.meta_info
        if(meta != None):
            meta_type = meta.meta_type

            # broadcasted routing packet
            # guaranteed to be a connected router
            if(meta_type == 1):
                otherRoutingTable = meta.meta_table[0]
                otherRouterID = packet.source.routerID

                # direct connection cost to determine if it's worth swapping our route
                connection = self.getConnectionFromNextID(otherRouterID)
                costToRouter = connection.cost

                # loop through the packet's routing table to update our own
                for i in range(len(otherRoutingTable)):
                    if(otherRoutingTable[i][0] == self.routerID): # skip own entry in their table
                        continue
                    destID = otherRoutingTable[i][0]
                    destCost = costToRouter + otherRoutingTable[i][1]

                    currentRoutingCost = self.routingTable[destID][1]
                    # we need to update cost for two cases:
                    # 1: the cost is just better
                    # 2: the update is from a path we're currently using for routing
                    costBetter = destCost < currentRoutingCost
                    costUpdate = (self.routingTable[destID][2] != None and otherRouterID == self.routingTable[destID][2].routerID)

                    if(costBetter or costUpdate):
                        self.timeSinceBroadcast = 1000
                    
                    if(costBetter): 
                        self.updateRoutingTable(destID, destCost, packet.source)
                    elif(costUpdate):
                        # if we're making an update, we should try to get other routers to propagate this information relative to distance
                        self.updateRoutingTable(destID, destCost, packet.source)

            # tracing packet
            if(meta_type == 2):
                if(packet.getDestinationID() != self.routerID):
                    nextRouterID = self.getNextRouterID(packet)
                    connection = self.getConnectionFromNextID(nextRouterID)
                    cost = connection.cost
                    # add self to the packet meta's trace list and cost of next path
                    packet.meta_info.meta_table[0].append(self.routerID)
                    packet.meta_info.meta_table[1] += cost
                else:
                    trace_table = packet.meta_info.meta_table[0]
                    trace_table.append(self.routerID)
                    # print out trace stack
                    Packet_META.PrintRoutingTrace(packet)
            
            # throttle packet
            if(meta_type == 3):
                if(packet.getDestinationID() == self.routerID):
                    throttlePercent = packet.meta_info.meta_table[0]
                    connection = self.getConnectionFromNextID(packet.getSourceID())
                    cID = self.connections.index(connection)
                    self.updateConnectionThrottle(cID, connection.throttlePercent * throttlePercent)
                    
                

    # broadcasts information about our routing information to connections
    def broadcastRoutingInfo(self):
        for i in range(len(self.connections)):
            newPacket = Packet_META_Crafter.RoutingInfoBroadcastPacket(self, self.connections[i].other, self.routingTable)
            self.connections[i].other.queuePacket(newPacket, self)

    # broadcasts a message to tell connections to lower the throughput to this router
    def broadcastRoutingFailure(self):
        for i in range(len(self.connections)):
            newPacket = Packet_META_Crafter.RoutingInfoThrottlePacket(self, self.connections[i].other, 0.5)
            self.connections[i].other.queuePacket(newPacket, self)

    # sends message to one connection to lower throughput
    def sendRoutingFailure(self, connection):
        newPacket = Packet_META_Crafter.RoutingInfoThrottlePacket(self, connection.other, 0.5)
        connection.other.queuePacket(newPacket, self)

    # update routing table entry
    def updateRoutingTable(self, id, newCost, newRouter):
        self.routingTable[id][1] = newCost
        self.routingTable[id][2] = newRouter

    # add direct connection to connections table
    def createConnection(self, other, throughput, failureRate):
        newConnection = Connection(other, throughput, failureRate)
        self.connections.append(newConnection)
        currentRoutingCost = self.routingTable[other.routerID][1]
        # update routing table if this route is better
        if(newConnection.cost < currentRoutingCost):
            self.updateRoutingTable(other.routerID, newConnection.cost, other)

    # time tick; handles queueing, sending, etc. for a point in time
    # also handles sending important information between routers
    def timeTick(self, time):
        # initialization
        shouldBroadcast = False
        if(time <= ROUTER_INTIALIZATION_TIME):
            # send routing packets based on if initializing network
            shouldBroadcast = self.timeSinceBroadcast >= ROUTER_INITIAL_BROADCAST_FREQUENCY
        else:
            shouldBroadcast = self.timeSinceBroadcast >= math.ceil(ROUTER_BROADCAST_FREQUENCY)
        
        # send routing table to connections if we should
        if (shouldBroadcast):
            self.broadcastRoutingInfo()
            self.timeSinceBroadcast = 0
        else:
            self.timeSinceBroadcast += 1

        if(time % ROUTER_THROUGHPUT_DECAY_FREQUENCY == 0):
            self.checkConnectionThrottles()

        newPacket = False
        # no packet in buffer, and we can get one
        if(self.currentPacket == None and len(self.queuedPackets) != 0):
            newPacket = True
            self.currentPacket = self.queuedPackets.pop(0)
            nextRouterID = self.getNextRouterID(self.currentPacket)
            self.queueSize -= self.currentPacket.size

            # couldn't find a route for this packet
            if(nextRouterID == -1):
                self.currentPacket = None
                print("Packet drop: no route found")
            else: # found route, set connection
                self.currentConnectionID = nextRouterID
                self.currentPacketProg = 0

        if( (self.currentPacket != None and not newPacket) or (self.currentPacket != None and newPacket and len(self.queuedPackets) != 0) ): # packet in buffer, sending
            nextRouterID = self.getNextRouterID(self.currentPacket)
            connection = self.getConnectionFromNextID(nextRouterID)
            throughput = connection.getThroughput()
            self.currentPacketProg += throughput
            # "send" packet to the next router to handle, get ready for next queued packet
            if(self.currentPacketProg > self.currentPacket.size):
                # process the meta if it's necessary
                hasMeta = self.currentPacket.meta_info != None
                if (hasMeta):
                    if(self.currentPacket.meta_info.requires_inspection):
                        self.processPacketMeta(self.currentPacket)

                nextRouter = connection.other
                nextRouter.queuePacket(self.currentPacket, self)
                self.currentPacket = None

    # adds packet to queue and queueSize if it can. drops packets if can't handle them
    def queuePacket(self, packet, sender):
        hasMeta = packet.meta_info != None
        # packet recieved and it's ours
        if (packet.destination == self):
            #print("Packet received: FROM RID #" + str(packet.source.routerID) + " TO RID #" + str(packet.destination.routerID) + ". ISMETA: " + str(hasMeta))

            self.processPacketMeta(packet)
            return


        packetSize = packet.size
        if (self.queueSize + packetSize < self.maxQueueSize):
            self.queuedPackets.append(packet)
            self.queueSize += packetSize
        else:
            connection = self.getConnectionFromNextID(sender.routerID)
            self.sendRoutingFailure(connection)
            print("Packet drop: queue size exceeded at r" + str(self.routerID) + ". Throttling connection to r" + str(sender.routerID))

    # returns the connection object for the given id
    def getConnectionFromNextID(self, id):
        for i in range(len(self.connections)):
            if (self.connections[i].other.routerID == id):
                return self.connections[i]
        return None

    # returns -1 if can't find a next router, otherwise
    # returns the router ID for the next router
    def getNextRouterID(self, packet):
        packetDestID = packet.getDestinationID()
        nextRouter = self.routingTable[packetDestID][2]
        if(nextRouter == None):
            return -1
        else:
            return nextRouter.routerID

    # returns true if routing table has a route to ID
    def doesRouteExist(self, id):
        return self.routingTable[id][2] != None

    # returns the value of the routing table's distance to ID
    def getDistanceToRouterID(self, id):
        return self.routingTable[id][1]
    

    
# helper class to contain source/dest of a packet, as well as size, carried information,
# and meta information for dynamic routing use
class Packet:
    def __init__(self, sourceRouter, destinationRouter, size, info, meta_info, isResponse):
        self.information = info
        self.meta_info = meta_info
        self.size = size
        self.destination = destinationRouter
        self.source = sourceRouter
        self.isResponse = isResponse

    def getSourceID(self):
        return self.source.routerID
    
    def getDestinationID(self):
        return self.destination.routerID

class Packet_META_Crafter:
    # see PACKET_META for packet information
    ROUTING_INFO_SIZE = 2

    # returns a crafted packet with meta information for a routing table information request
    # need to include a path cost if this is a response
    def RoutingInfoPacket(sourceRouter, destRouter, routingID, isResponse, pathCost = -1):
        meta_table = []
        if(not isResponse):
            meta_table = [routingID]
        else:
            if(pathCost == -1):
                print("Fatal Error crafting routing packet: no path cost provided")
                return None
            meta_table = [routingID, pathCost]
        
        packet_meta = Packet_META(0, meta_table, False)
        newPacket = Packet(sourceRouter, destRouter, Packet_META_Crafter.ROUTING_INFO_SIZE, None, packet_meta, isResponse)
        return newPacket

    # returns a crafted packet with meta information for a broadcasted routing table entry
    def RoutingInfoBroadcastPacket(sourceRouter, destRouter, routingTable):
        meta_table = [routingTable]
        
        packet_meta = Packet_META(1, meta_table, False)
        newPacket = Packet(sourceRouter, destRouter, Packet_META_Crafter.ROUTING_INFO_SIZE + len(meta_table), None, packet_meta, True)
        return newPacket

    # returns a crafted packet with meta information for a tracing packet
    # should add every router's distance to it on transmission
    def RoutingInfoTracePacket(sourceRouter, destRouter):
        meta_table = [ [], 0 ]
        
        packet_meta = Packet_META(2, meta_table, True)
        newPacket = Packet(sourceRouter, destRouter, Packet_META_Crafter.ROUTING_INFO_SIZE + len(meta_table), None, packet_meta, True)
        return newPacket

    # returns a crafted packet with meta information for a throttle packet
    def RoutingInfoThrottlePacket(sourceRouter, destRouter, percentage):
        meta_table = [percentage]
        
        packet_meta = Packet_META(3, meta_table, False)
        newPacket = Packet(sourceRouter, destRouter, Packet_META_Crafter.ROUTING_INFO_SIZE + len(meta_table), None, packet_meta, True)
        return newPacket

class Packet_META:
    # meta_types:
    # comments give meta_type as an ID number, the information they are supposed to represent,
    # and below them is the data that goes in the meta_table. 
    #
    # 0 --> routing information request/response for routing table
    #       REQUEST:  [routerID]
    #       RESPONSE: [routerID, cost]
    # 1 --> routing information broadcast for routing table
    #       REQUEST:  unused
    #       RESPONSE: [routingTable]
    # 2 --> routing trace packet
    #       REQUEST:  unused
    #       RESPONSE: [ [r1, r2, r3, ...], [totalCost] ] list of routers traversed, and a cumulative cost
    # 3 --> throttle packet
    #       REQUEST: unused
    #       RESPONSE: [percentage] percent to set connection throughput to between these two routers
    def __init__(self, meta_type, meta_table, requires_inspection):
        self.meta_type = meta_type
        self.meta_table = meta_table
        self.requires_inspection = requires_inspection # indicates that every router must evaluate this packet

    def PrintRoutingTrace(packet):
        trace_table = packet.meta_info.meta_table[0]
        total_cost = str(packet.meta_info.meta_table[1])
        trace = ""
        sourceID = packet.getSourceID()
        destID = packet.getDestinationID()
        trace += "Routing Trace Packet from r" + str(sourceID) + " to r" + str(destID) + "\n";
        trace += "Routing Trace Stack: "
        # print out trace stack
        for i in range(len(trace_table)):
            trace += "r" + str(trace_table[i])
            if(i != len(trace_table) - 1):
                trace += " -> "
        trace += ", cost: " + str(total_cost)
        print(trace)



# helper class to define the properties of a connection between two routers
class Connection:
    def __init__(self, otherRouter, throughput, failureRate):
        self.other = otherRouter
        self.throughput = throughput
        self.failureRate = failureRate
        self.cost = 100 * 1/throughput
        self.throughputPercent = 1
        self.throttlePercent = 1

    def updateThroughputPercent(self, percent):
        self.throughputPercent = percent
        self.cost = 100 * 1 / (self.throughput * self.throughputPercent * self.throttlePercent)

    def updateThrottlePercent(self, percent):
        self.throttlePercent = percent
        self.cost = 100 * 1 / (self.throughput * self.throughputPercent * self.throttlePercent)

    def getThroughput(self):
        return self.throughput * self.throughputPercent * self.throttlePercent

    def getThroughputPercent(self):
        return self.throughputPercent

    def connectionSuccess(self):
        success = random.random() > self.failureRate
        return success

