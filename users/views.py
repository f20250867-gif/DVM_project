from django.contrib.auth import authenticate, get_user_model
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from .serializers import UserSerializer
from rest_framework.permissions import IsAuthenticated
from .models import Node, Edge, Trip
from .serializers import NodeSerializer, EdgeSerializer, TripSerializer
from .utils import calculate_detour_and_fare, shortest_path
from .models import RideRequest
from .serializers import RideRequestSerializer
from .utils import find_matching_trips
from django.db import transaction
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.decorators import login_required
from .utils import get_remaining_route, is_request_matching_trip
from .models import RideOffer, Node
from .permissions import IsServiceActive

def home_page(request):
    return render(request, 'users/home.html')

def register_page_ui(request):
    return render(request, 'users/register.html')

class LoginView(APIView):

    def post(self, request):

        username = request.data.get("username")
        password = request.data.get("password")

        user = authenticate(username=username, password=password)

        if user is None:
            return Response({"error": "Invalid credentials"}, status=401)

        refresh = RefreshToken.for_user(user)

        return Response({
            "refresh": str(refresh),
            "access": str(refresh.access_token),
            "role": user.role
        })


User = get_user_model()

def register_user(request):

    if request.method == "POST":

        username = request.POST.get("username")
        password = request.POST.get("password")
        role = request.POST.get("role")

        user = User.objects.create_user(
            username=username,
            password=password
        )

        user.role = role
        user.save()

        #redirection
        if role == "driver":
            return redirect("/api/driver/home/")
        else:
            return redirect("/api/passenger/dashboard/")

    return redirect("/api/signup/")
class MeView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):

        user = request.user

        data = {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role
        }

        return Response(data)
    
#node api view 
class NodeView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):

        nodes = Node.objects.all()
        serializer = NodeSerializer(nodes, many=True)

        return Response(serializer.data)


    def post(self, request):

        serializer = NodeSerializer(data=request.data)

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)

        return Response(serializer.errors)

#edge api view
class EdgeView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):

        edges = Edge.objects.all()
        serializer = EdgeSerializer(edges, many=True)

        return Response(serializer.data)


    def post(self, request):

        serializer = EdgeSerializer(data=request.data)

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)

        return Response(serializer.errors)
    
#trip api
class TripView(APIView):
    permission_classes = [IsAuthenticated, IsServiceActive]

    def get(self, request):

        trips = Trip.objects.all()
        serializer = TripSerializer(trips, many=True)

        return Response(serializer.data)


    def post(self, request):

        serializer = TripSerializer(data=request.data)

        if serializer.is_valid():

            start = int(request.data.get("start_node"))
            end = int(request.data.get("end_node"))

            distance, path = shortest_path(start, end)

            if not path:
                return Response({"error": "No route found"})

            trip = serializer.save(
                driver=request.user,
                route=path,
                available_seats=request.data.get("max_passengers"),
                visited_nodes=[path[0]],#first node is the starting point
                current_node_id=path[0]#initialize current node to starting point
            )
            
            return Response(serializer.data)

        return Response(serializer.errors)
    
#shortest path api
class RouteView(APIView):

    def get(self, request):

        start = int(request.GET.get("start"))
        end = int(request.GET.get("end"))

        distance, path = shortest_path(start, end)

        return Response({
            "distance": distance,
            "path": path
        })
    

#ride request api
class RideRequestView(APIView):

    permission_classes = [IsAuthenticated, IsServiceActive]

    def post(self, request):

        serializer = RideRequestSerializer(data=request.data)

        if serializer.is_valid():

            ride_request = serializer.save(passenger=request.user)

            matches = find_matching_trips(
                ride_request.pickup_node.id,
                ride_request.drop_node.id
            )

            return Response({
                "ride_request": serializer.data,
                "matches": matches
            })

        return Response(serializer.errors)

#accept ride api
class AcceptRideView(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request):

        ride_request_id = request.data.get("ride_request_id")
        trip_id = request.data.get("trip_id")

        ride_request = get_object_or_404(RideRequest, id=ride_request_id)

        with transaction.atomic():

            trip = Trip.objects.select_for_update().get(id=trip_id)

            if trip.available_seats <= 0:
                return Response({"error": "Trip is full"})

            trip.available_seats -= 1
            trip.save()

            ride_request.status = "matched"
            ride_request.save()

        return Response({
            "message": "Ride confirmed",
            "trip_id": trip.id
        })
#cancel trip api
class CancelTripView(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request):

        trip_id = request.data.get("trip_id")
        trip = Trip.objects.get(id=trip_id)

        if trip.driver != request.user:
            return Response({"error": "Only driver can cancel trip"})
        trip.delete()

        return Response({"message": "Trip cancelled successfully"})

#update location api
class UpdateLocationView(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request):

        trip_id = request.data.get("trip_id")
        node_id = request.data.get("node_id")
        
        trip = Trip.objects.get(id=trip_id)

        if trip.driver != request.user:
            return Response({"error": "Not allowed"})
        
        route = trip.route or []
        visited = trip.visited_nodes or []

        if node_id not in route:
            return Response({"error": "Invalid node for this trip"})

        last_index = route.index(visited[-1])
        new_index = route.index(node_id)

        if new_index <= last_index:
            return Response({"error": "Cannot revisit or go backwards"})

        new_visited = route[:new_index + 1]

        trip.visited_nodes = new_visited
        trip.current_node_id = node_id
        trip.save()

        return Response({
            "message": "Location updated",
            "current_node": node_id,
            "visited_nodes": new_visited
        })
    


class DriverRequestsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, trip_id):
        trip = get_object_or_404(Trip, id=trip_id, driver=request.user)
        pending_requests = RideRequest.objects.filter(status="pending")
        
        valid_requests_data = []
        for req in pending_requests:
            if is_request_matching_trip(trip, req.pickup_node_id, req.drop_node_id):
                # Calculate the specific detour and fare
                detour, fare = calculate_detour_and_fare(trip, req)
                
                # Convert the request to a dictionary and inject our new calculations
                req_data = RideRequestSerializer(req).data
                req_data['detour_nodes'] = detour
                req_data['calculated_fare'] = fare
                
                valid_requests_data.append(req_data)
                
        return Response(valid_requests_data)

@login_required
def driver_dashboard_ssr(request, trip_id):
    trip = get_object_or_404(Trip, id=trip_id, driver=request.user)
    pending_requests = RideRequest.objects.filter(status="pending")
    
    valid_requests = []
    for req in pending_requests:
        if is_request_matching_trip(trip, req.pickup_node_id, req.drop_node_id):
            detour, fare = calculate_detour_and_fare(trip, req)
            
            # Dynamically attach the variables to the object so the template can read them
            req.detour = detour
            req.fare = fare
            valid_requests.append(req)
            
    context = {
        "trip": trip,
        "remaining_route": get_remaining_route(trip),
        "requests": valid_requests
    }
    return render(request, "users/templates/users/driver_dashboard.html", context)



class MakeOfferView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        ride_request_id = request.data.get("ride_request_id")
        trip_id = request.data.get("trip_id")

        # 1. Fetch the objects first
        ride_request = get_object_or_404(RideRequest, id=ride_request_id)
        trip = get_object_or_404(Trip, id=trip_id, driver=request.user)

        if trip.available_seats <= 0:
            return Response({"error": "Trip is full"}, status=400)
            
        if RideOffer.objects.filter(ride_request=ride_request, trip=trip).exists():
            return Response({"error": "You already made an offer for this request."}, status=400)

        # Calculate the detour and fare using the same logic as the dashboard
        detour_val, fare_val = calculate_detour_and_fare(trip, ride_request)

        #Create the offer with the dynamically generated numbers
        offer = RideOffer.objects.create(
            ride_request=ride_request,
            trip=trip,
            proposed_fare=fare_val,       
            detour_nodes=detour_val       
        )

        return Response({"message": "Offer sent to passenger successfully!", "offer_id": offer.id})


# 2. SSR View for the Driver Dashboard
@login_required
def driver_dashboard_ssr(request, trip_id):
    trip = get_object_or_404(Trip, id=trip_id, driver=request.user)
    
    # 1. Fetch raw incoming requests
    base_requests = RideRequest.objects.filter(status="pending").exclude(offers__trip=trip)
    
    incoming_requests = []
    
    # 2. Loop through them and run your math formula!
    for req in base_requests:
        # Calculate the dynamic fare and detour
        detour, fare = calculate_detour_and_fare(trip, req)
        
        # Attach the numbers to the object so the HTML can display them
        req.detour = detour
        req.fare = fare
        
        incoming_requests.append(req)

    # Categorize the driver's offers
    pending_offers = RideOffer.objects.filter(trip=trip, status="pending")
    confirmed_carpools = RideOffer.objects.filter(trip=trip, status="accepted")
    past_offers = RideOffer.objects.filter(trip=trip, status="rejected")

    context = {
        "trip": trip,
        "incoming_requests": incoming_requests, # Now contains the calculated fares!
        "pending_offers": pending_offers,
        "confirmed_carpools": confirmed_carpools,
        "past_offers": past_offers
    }
    return render(request, "users/driver_dashboard.html", context)

class AcceptOfferView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, offer_id):
        # 1. Find the offer, and ensure the person clicking "accept" is the actual passenger!
        offer = get_object_or_404(RideOffer, id=offer_id, ride_request__passenger=request.user)

        if offer.status != 'pending':
            return Response({"error": f"This offer is already {offer.status}."}, status=400)

        trip = offer.trip

        # 2. Check if the driver's car is full
        if trip.available_seats <= 0:
            return Response({"error": "Sorry, this trip is already full."}, status=400)

        # 3. Accept the offer
        offer.status = 'accepted'
        offer.save()

        # 4. Mark the passenger's request as matched
        ride_request = offer.ride_request
        ride_request.status = 'matched'
        ride_request.save()

        # 5. Decrease the available seats in the car
        trip.available_seats -= 1
        trip.save()

        # 6. Auto-reject any OTHER offers from different drivers for this exact request
        RideOffer.objects.filter(
            ride_request=ride_request, 
            status='pending'
        ).exclude(id=offer.id).update(status='rejected')

        return Response({
            "message": "Offer accepted successfully! Your ride is confirmed.",
            "trip_id": trip.id
        })

@login_required
def passenger_dashboard_ssr(request):
    # 1. If they already have a pending request, redirect them instantly to the offers page
    active_request = RideRequest.objects.filter(passenger=request.user, status='pending').first()
    if active_request:
        return redirect('passenger-offers', request_id=active_request.id)

    # 2. Handle the form submission to create a new request
    if request.method == 'POST':
        pickup_id = request.POST.get('pickup_node')
        drop_id = request.POST.get('drop_node')
        
        pickup_node = get_object_or_404(Node, id=pickup_id)
        drop_node = get_object_or_404(Node, id=drop_id)
        
        new_req = RideRequest.objects.create(
            passenger=request.user,
            pickup_node=pickup_node,
            drop_node=drop_node
        )
        # Redirect to the offers page
        return redirect('passenger-offers', request_id=new_req.id)

    # 3. If it's a normal GET request, show the booking form
    nodes = Node.objects.all()
    return render(request, 'users/passenger_dashboard.html', {'nodes': nodes})

@login_required
def passenger_offers_ssr(request, request_id):
    ride_request = get_object_or_404(RideRequest, id=request_id, passenger=request.user)
    
    # Get all pending offers for this specific request
    offers = RideOffer.objects.filter(ride_request=ride_request, status='pending')
    
    context = {
        'ride_request': ride_request,
        'offers': offers
    }
    return render(request, 'users/passenger_offers.html', context)

@login_required
def passenger_cancel_request(request, request_id):
    if request.method == 'POST':
        ride_request = get_object_or_404(RideRequest, id=request_id, passenger=request.user)
        
        ride_request.delete()
    return redirect('passenger-dashboard')

@login_required
def passenger_accept_offer(request, offer_id):
    if request.method == 'POST':
        offer = get_object_or_404(RideOffer, id=offer_id, ride_request__passenger=request.user)
        
        if offer.status == 'pending' and offer.trip.available_seats > 0:
            # 1. Accept this offer
            offer.status = 'accepted'
            offer.save()
            
            # 2. Mark request as matched
            req = offer.ride_request
            req.status = 'matched'
            req.save()
            
            # 3. Reduce car seats
            trip = offer.trip
            trip.available_seats -= 1
            trip.save()
            
            # 4. Reject all other drivers' offer
            RideOffer.objects.filter(ride_request=req, status='pending').exclude(id=offer.id).update(status='rejected')

    return redirect('passenger-dashboard')


@login_required
def driver_home_ssr(request):

    user = request.user

    if user.role != "driver":
        return redirect("/api/passenger/dashboard/")

    # ✅ HANDLE FORM SUBMISSION
    if request.method == "POST":

        start = int(request.POST.get("start_node"))
        end = int(request.POST.get("end_node"))
        seats = int(request.POST.get("available_seats"))
        max_passenger = int(request.POST.get("max_passengers"))

        from .utils import shortest_path

        distance, path = shortest_path(start, end)

        trip = Trip.objects.create(
            driver=user,
            start_node_id=start,
            end_node_id=end,
            route=path,
            available_seats=seats,
            max_passengers=max_passenger,
        )

        return redirect(f"/api/trips/dashboard/{trip.id}/")

    # ✅ HANDLE PAGE LOAD
    nodes = Node.objects.all()
    trips = Trip.objects.filter(driver=user)

    trip_data = []

    nodes = Node.objects.all()
    trips = Trip.objects.filter(driver=user)

    trip_data = []

    for trip in trips:

        has_requests = RideRequest.objects.filter(
            pickup_node__in=trip.route,
            drop_node__in=trip.route,
            status="pending"
        ).exists()

        trip_data.append({
            "trip": trip,
            "has_requests": has_requests
        })

    return render(request, "users/driver_home.html", {
        "nodes": nodes,
        "trip_data": trip_data
    })



@login_required
def role_redirect_view(request):
    user = request.user
#saving choice to the database
    if request.method == 'POST':
        selected_role = request.POST.get('role')
        if selected_role in ['driver', 'passenger']:
            user.role = selected_role
            user.save()
            # After saving, let the logic below redirect them properly

    if user.role == 'driver':
        return redirect('driver-home')
    elif user.role == 'passenger':
        return redirect('passenger-dashboard')
        
    return render(request, 'users/choose_role.html')