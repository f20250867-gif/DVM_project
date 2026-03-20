import heapq
from .models import Edge, Trip, RideOffer
from django.db.models import F

def build_graph():
    graph = {}

    edges = Edge.objects.all()

    for edge in edges:
        start = edge.from_node.id
        end = edge.to_node.id
        distance = edge.distance

        if start not in graph:
            graph[start] = []

        graph[start].append((end, distance))

    return graph

#dijkstra's algorithm to find the shortest path from source to destination
def shortest_path(start, end):

    graph = build_graph()

    queue = [(0, start, [])]
    visited = set()

    while queue:

        distance, node, path = heapq.heappop(queue)

        if node in visited:
            continue

        visited.add(node)
        path = path + [node]

        if node == end:
            return distance, path

        for neighbor, weight in graph.get(node, []):
            heapq.heappush(queue, (distance + weight, neighbor, path))

    return None, []



#function to find matching trips for a given pickup and drop node


def get_remaining_route(trip):
# Returns the remaining route for a trip based on the driver's current location.
    route = trip.route or []
    visited = trip.visited_nodes or []
    
    if not visited:
        return route
        
    last_visited = visited[-1]
    try:
        idx = route.index(last_visited)
        return route[idx:] 
    except ValueError:
        return route

def get_reachable_nodes(start_id, max_hops=2, reverse_graph=False):
 # Returns a set of node IDs that are reachable from the start_id within max_hops.
    adj_list = {}
    edges = Edge.objects.all()
    
    for edge in edges:
        u, v = edge.from_node_id, edge.to_node_id
        if reverse_graph:
            adj_list.setdefault(v, []).append(u)
        else:
            adj_list.setdefault(u, []).append(v)
            
    visited = {start_id}
    queue = [(start_id, 0)]
    
    while queue:
        curr, hops = queue.pop(0)
        if hops < max_hops:
            for neighbor in adj_list.get(curr, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, hops + 1))
                    
    return visited

def is_request_matching_trip(trip, pickup_node_id, drop_node_id):
 # 1. Check if the trip has available seats
    if trip.available_seats <= 0:
        return False
        
    # If the driver has already passed the drop-off point, it's not a match
    if trip.current_node_id == trip.end_node_id:
        return False

    remaining_route = get_remaining_route(trip)
    
    #   The pickup and drop must both be on the remaining route, and pickup must come before drop
    if pickup_node_id in remaining_route and drop_node_id in remaining_route:
        pickup_index = remaining_route.index(pickup_node_id)
        drop_index = remaining_route.index(drop_node_id)
        
        # Ensure the driver reaches the pickup BEFORE the drop-off
        if pickup_index < drop_index:
            return True
            
    return False

def find_matching_trips(pickup_node_id, drop_node_id):

    matches = []

    active_trips = Trip.objects.filter(available_seats__gt=0).exclude(current_node_id=F('end_node_id'))
    
    for trip in active_trips:
        if is_request_matching_trip(trip, pickup_node_id, drop_node_id):
            matches.append({
                "trip_id": trip.id,
                "driver": trip.driver.username,
                "remaining_route": get_remaining_route(trip)
            })
    return matches




def calculate_all_fares(trip, new_route, all_requests):
    """
    Calculates fares for all passengers sharing the route.
    Applies the distance-based fare formula: 
    p = 30 * distance, base = 200
    """
    base_fee = 200.0 # New Base Fee
    
    # Initialize the fare dictionary for every passenger with the new base fee
    fares = {req.id: base_fee for req in all_requests}
    
    # Iterate over every single hop (edge) in the new route
    for i in range(len(new_route) - 1):
        u = new_route[i]
        v = new_route[i+1]
        
        # 1. Calculate the distance of this hop (u to v)
        # We check both directions just in case your graph edges are undirected
        edge = Edge.objects.filter(from_node_id=u, to_node_id=v).first()
        if not edge:
            edge = Edge.objects.filter(from_node_id=v, to_node_id=u).first()
            
        # Fallback to a distance of 1.0 if an edge is somehow missing
        distance = edge.distance if edge else 1.0 
        
        # Calculate dynamic price per hop (p)
        p = 30.0 * distance
        
        passengers_in_this_hop = []
        
        # 2. Check which passengers are physically in the car
        for req in all_requests:
            req_pickup = req.pickup_node.id
            req_drop = req.drop_node.id
            
            pickup_idx = 0 
            if req_pickup in new_route:
                pickup_idx = new_route.index(req_pickup)
            elif req_pickup in (trip.visited_nodes or []):
                pickup_idx = 0
                
            drop_idx = len(new_route) - 1
            if req_drop in new_route:
                drop_idx = new_route.index(req_drop)
            
            if pickup_idx <= i and drop_idx >= i + 1:
                passengers_in_this_hop.append(req.id)
        
        n_i = len(passengers_in_this_hop)
        
        # 3. Apply the split-fare formula
        if n_i > 0:
            cost_per_person = p * (1.0 / n_i)
            for req_id in passengers_in_this_hop:
                fares[req_id] += cost_per_person
                
    return fares


def calculate_detour_and_fare(trip, ride_request):

    remaining_route = get_remaining_route(trip)
    
    if not remaining_route:
        return 0, 0
        
    current_node_id = remaining_route[0]
    pickup_node_id = ride_request.pickup_node.id
    drop_node_id = ride_request.drop_node.id
    end_node_id = remaining_route[-1]
    
    # 1. Calculate the distance of the driver's remaining route
    original_remaining_dist = 0
    for i in range(len(remaining_route) - 1):
        u = remaining_route[i]
        v = remaining_route[i+1]
        edge = Edge.objects.filter(from_node_id=u, to_node_id=v).first() or Edge.objects.filter(from_node_id=v, to_node_id=u).first()
        original_remaining_dist += (edge.distance if edge else 1.0)

    # 2. Calculate the new distance if they pick up this passenger from their current location
    dist_to_pickup, path_to_pickup = shortest_path(current_node_id, pickup_node_id)
    dist_passenger, path_passenger = shortest_path(pickup_node_id, drop_node_id)
    dist_to_end, path_to_end = shortest_path(drop_node_id, end_node_id)
    
    if path_to_pickup is None or path_passenger is None or path_to_end is None:
        return float('inf'), 0
        
    new_remaining_dist = dist_to_pickup + dist_passenger + dist_to_end
    
    # 3. Detour = Difference between the new remaining journey and the old remaining journey
    detour = max(0, new_remaining_dist - original_remaining_dist)
    
    # Construct the full new proposed route (removing overlapping nodes)
    new_route = path_to_pickup[:-1] + path_passenger[:-1] + path_to_end
    
    accepted_offers = RideOffer.objects.filter(trip=trip, status="accepted")
    confirmed_requests = [offer.ride_request for offer in accepted_offers]

    # Combine existing passengers with the new requesting passenger
    all_requests = confirmed_requests + [ride_request]
    
    # Calculate the dynamic fares for EVERYONE
    all_fares = calculate_all_fares(trip, new_route, all_requests)
    passenger_fare = all_fares.get(ride_request.id, 0.0)
    
    return round(detour, 2), round(passenger_fare, 2)