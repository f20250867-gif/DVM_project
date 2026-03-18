from .models import Edge
import heapq


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


from .models import Trip
from .utils import shortest_path

#function to find matching trips for a given pickup and drop node
def find_matching_trips(pickup_node, drop_node):

    matches = []

    trips = Trip.objects.all()

    for trip in trips:

        distance, path = shortest_path(
            trip.start_node.id,
            trip.end_node.id
        )

        if pickup_node in path and drop_node in path:

            pickup_index = path.index(pickup_node)
            drop_index = path.index(drop_node)

            if pickup_index < drop_index:
                matches.append({
                    "trip_id": trip.id,
                    "driver": trip.driver.username,
                    "route": path
                })

    return matches