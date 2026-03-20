from django.contrib.auth import authenticate, get_user_model
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from .serializers import UserSerializer
from rest_framework.permissions import IsAuthenticated
from .models import Node, Edge, Trip,RideOffer, RideRequest, Transaction
from .serializers import NodeSerializer, EdgeSerializer, TripSerializer
from .utils import calculate_detour_and_fare, shortest_path
from .serializers import RideRequestSerializer
from .utils import find_matching_trips
from django.db import transaction
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.decorators import login_required
from .utils import get_remaining_route, is_request_matching_trip
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
    permission_classes = [IsAuthenticated]

    # 1. View all their active and past trips
    def get(self, request):
        if request.user.role != 'driver':
            return Response({"error": "Only drivers can view their trips."}, status=status.HTTP_403_FORBIDDEN)
        
        # Filter trips by the currently logged-in driver, order by newest first
        trips = Trip.objects.filter(driver=request.user).order_by('-created_at')
        serializer = TripSerializer(trips, many=True)
        return Response(serializer.data)

    # 2. Publish a new trip and generate route
    def post(self, request):
        if request.user.role != 'driver':
            return Response({"error": "Only drivers can publish trips."}, status=status.HTTP_403_FORBIDDEN)

        serializer = TripSerializer(data=request.data)

        if serializer.is_valid():
            # Extract data from request
            start_id = int(request.data.get("start_node"))
            end_id = int(request.data.get("end_node"))
            max_passengers = int(request.data.get("max_passengers"))

            #generate route using Dijkstra's algorithm
            distance, path = shortest_path(start_id, end_id)

            if not path:
                return Response({"error": "No valid route found between these nodes."}, status=status.HTTP_400_BAD_REQUEST)

            #saving trips to the database
            trip = serializer.save(
                driver=request.user,
                route=path,
                available_seats=max_passengers, # Initially, available seats = max passengers
                visited_nodes=[path[0]],        # Mark the start node as visited
                current_node_id=path[0]         # Set current node to the start node
            )
            
            return Response(TripSerializer(trip).data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
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

    #cancel trip before departure
    def post(self, request):
        trip_id = request.data.get("trip_id")
        
        try:
            trip = Trip.objects.get(id=trip_id)
        except Trip.DoesNotExist:
            return Response({"error": "Trip not found"}, status=status.HTTP_404_NOT_FOUND)

        # Ensure the user requesting cancellation is the driver
        if trip.driver != request.user:
            return Response({"error": "Only the driver of this trip can cancel it."}, status=status.HTTP_403_FORBIDDEN)

        #checking : A trip can only be cancelled if it hasn't started. 
        # It hasn't started if the current node is still the start node, and only 1 node is visited.
        if len(trip.visited_nodes) > 1 or trip.current_node_id != trip.start_node_id:
            return Response(
                {"error": "Cannot cancel a trip that has already started. You are currently en route."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        trip.delete()
        return Response({"message": "Trip cancelled successfully before departure."}, status=status.HTTP_200_OK)

#update location api
class UpdateLocationView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        trip_id = request.data.get("trip_id")
        
        try:
            node_id = int(request.data.get("node_id"))
        except (TypeError, ValueError):
            return Response({"error": "Invalid node_id format."}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            trip = Trip.objects.get(id=trip_id)
        except Trip.DoesNotExist:
            return Response({"error": "Trip not found"}, status=status.HTTP_404_NOT_FOUND)

        if trip.driver != request.user:
            return Response({"error": "Not allowed. You are not the driver."}, status=status.HTTP_403_FORBIDDEN)
        
        route = trip.route or []
        visited = trip.visited_nodes or []

        if node_id not in route:
            return Response({"error": "Invalid node. This node is not on your planned route."}, status=status.HTTP_400_BAD_REQUEST)

        # Fallback just in case visited is somehow empty
        last_index = route.index(visited[-1]) if visited else -1
        new_index = route.index(node_id)

        
        if new_index <= last_index:
            return Response({"error": "Cannot revisit a previous node or go backwards."}, status=status.HTTP_400_BAD_REQUEST)

        # Update visited nodes by slicing the route array up to the new node
        new_visited = route[:new_index + 1]

        trip.visited_nodes = new_visited
        trip.current_node_id = node_id
        trip.save()
        
        # Check if they reached the end
        message = "Location updated successfully."
        if node_id == trip.end_node_id:
            message = "Destination reached! Trip is now complete."

        if node_id == trip.end_node_id:
            accepted_offers = RideOffer.objects.filter(trip=trip, status='accepted')
            
            #Check if any passenger is broke
            insufficient_passengers = []
            for offer in accepted_offers:
                if offer.ride_request.passenger.wallet_balance < offer.proposed_fare:
                    insufficient_passengers.append(offer.ride_request.passenger.username)
                    
            if insufficient_passengers:
                #If any passenger can't pay, we should not complete the trip 
                return Response({
                    "error": f"Trip cannot be completed. The following passengers have insufficient balance: {', '.join(insufficient_passengers)}."
                }, status=status.HTTP_400_BAD_REQUEST)
                
            #Deduct fares and award the driver securely
            with transaction.atomic():
                total_earnings = 0.0
                
                for offer in accepted_offers:
                    passenger = offer.ride_request.passenger
                    fare = offer.proposed_fare
                    
                    #Deduct from passenger
                    passenger.wallet_balance -= fare
                    passenger.save()
                    Transaction.objects.create(
                        user=passenger, amount=fare, transaction_type='deduction', trip=trip
                    )
                    
                    total_earnings += fare
                    
                #earnings to the driver
                if total_earnings > 0:
                    trip.driver.wallet_balance += total_earnings
                    trip.driver.save()
                    Transaction.objects.create(
                        user=trip.driver, amount=total_earnings, transaction_type='earning', trip=trip
                    )
                    
            message = "Destination reached! Trip complete and fares have been settled."
        else:
            message = "Location updated successfully."

        # Proceed to update the actual node locations if payments passed (or weren't needed yet)
        new_visited = route[:new_index + 1]
        trip.visited_nodes = new_visited
        trip.current_node_id = node_id
        trip.save()

        return Response({
            "message": message,
            "current_node": node_id,
            "visited_nodes": new_visited
        }, status=status.HTTP_200_OK)

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
    
 
    incoming_requests = []
    if trip.current_node_id != trip.end_node_id:
        base_requests = RideRequest.objects.filter(status="pending").exclude(offers__trip=trip)
        
        for req in base_requests:
            if is_request_matching_trip(trip, req.pickup_node.id, req.drop_node.id):
                detour, fare = calculate_detour_and_fare(trip, req)
                req.detour = detour
                req.fare = fare
                incoming_requests.append(req)

    pending_offers = RideOffer.objects.filter(trip=trip, status="pending")
    confirmed_carpools = RideOffer.objects.filter(trip=trip, status="accepted")
    past_offers = RideOffer.objects.filter(trip=trip, status="rejected")

    context = {
        "trip": trip,
        "incoming_requests": incoming_requests, 
        "pending_offers": pending_offers,
        "confirmed_carpools": confirmed_carpools,
        "past_offers": past_offers
    }
    return render(request, "users/driver_dashboard.html", context)



class MakeOfferView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):

        trip_id = request.data.get("trip_id")
        ride_request_id = request.data.get("ride_request_id")

        trip = Trip.objects.get(id=trip_id)
        ride_request = RideRequest.objects.get(id=ride_request_id)

        from .utils import calculate_detour_and_fare

        detour, fare = calculate_detour_and_fare(trip, ride_request)

        offer = RideOffer.objects.create(
            trip=trip,
            ride_request=ride_request,
            proposed_fare=fare, 
            status="pending"
        )

        return Response({
            "message": "Offer created",
            "fare": fare
        })

#SSR View for the Driver Dashboard
@login_required
def driver_dashboard_ssr(request, trip_id):
    trip = get_object_or_404(Trip, id=trip_id, driver=request.user)
    

    base_requests = RideRequest.objects.filter(status="pending").exclude(offers__trip=trip)
    
    incoming_requests = []
    
        # For each request, check if it matches the trip and calculate detour/fare
    for req in base_requests:
        if is_request_matching_trip(trip, req.pickup_node.id, req.drop_node.id):
            
            #calculate the specific detour and fare for this request
            detour, fare = calculate_detour_and_fare(trip, req)
            
            # Attach the numbers to the object so the HTML can display them
            req.detour = detour
            req.fare = fare
            
            incoming_requests.append(req)

    #Categorize the driver's offers
    pending_offers = RideOffer.objects.filter(trip=trip, status="pending")
    confirmed_carpools = RideOffer.objects.filter(trip=trip, status="accepted")
    past_offers = RideOffer.objects.filter(trip=trip, status="rejected")

    context = {
        "trip": trip,
        "incoming_requests": incoming_requests, # Now safely filtered!
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

        #Check if the driver's car is full
        if trip.available_seats <= 0:
            return Response({"error": "Sorry, this trip is already full."}, status=400)

        #Accept the offer
        offer.status = 'accepted'
        offer.save()

        #Mark the passenger's request as matched
        ride_request = offer.ride_request
        ride_request.status = 'matched'
        ride_request.save()

        #Decrease the available seats in the car
        trip.available_seats -= 1
        trip.save()

        #Auto-reject any OTHER offers from different drivers for this exact request
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
    #If they already have a pending request, redirect them instantly to the offers page
    active_request = RideRequest.objects.filter(passenger=request.user, status='pending').first()
    if active_request:
        return redirect('passenger-offers', request_id=active_request.id)

    #Handle the form submission to create a new request
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

    #If it's a normal GET request, show the booking form
    nodes = Node.objects.all()
    return render(request, 'users/passenger_dashboard.html', {'nodes': nodes})

@login_required
def passenger_offers_ssr(request, request_id):
    ride_request = get_object_or_404(RideRequest, id=request_id, passenger=request.user)
    
    #Get all pending offers for this specific request
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
            #Accept this offer
            offer.status = 'accepted'
            offer.save()
            
            #Mark request as matched
            req = offer.ride_request
            req.status = 'matched'
            req.save()
            
            #Reduce car seats
            trip = offer.trip
            trip.available_seats -= 1
            trip.save()
            
            #Reject all other drivers' offer
            RideOffer.objects.filter(ride_request=req, status='pending').exclude(id=offer.id).update(status='rejected')

    return redirect('passenger-dashboard')


@login_required
def driver_home_ssr(request):

    user = request.user

    if user.role != "driver":
        return redirect("/api/passenger/dashboard/")

#Handle new trip creation
    if request.method == "POST":

        start = int(request.POST.get("start_node"))
        end = int(request.POST.get("end_node"))
        seats = int(request.POST.get("available_seats"))
        max_passenger = int(request.POST.get("max_passengers"))

        distance, path = shortest_path(start, end)

        trip = Trip.objects.create(
            driver=user,
            start_node_id=start,
            end_node_id=end,
            route=path,
            available_seats=seats,
            max_passengers=max_passenger,
            current_node_id=start,  
            visited_nodes=[start]   
        )

        return redirect(f"/api/trips/dashboard/{trip.id}/")

 
    nodes = Node.objects.all()
    trips = Trip.objects.filter(driver=user)

    trip_data = []

    nodes = Node.objects.all()
    trips = Trip.objects.filter(driver=user)

    trip_data = []

    #FILTERING LOGIC 
    all_requests = RideRequest.objects.filter(status="pending")

    for trip in trips:

        has_requests = False

        for req in all_requests:
            if is_request_matching_trip(trip, req.pickup_node.id, req.drop_node.id):
                has_requests = True
                break

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
            # After saving the role, redirect to the appropriate dashboard

    if user.role == 'driver':
        return redirect('driver-home')
    elif user.role == 'passenger':
        return redirect('passenger-dashboard')
        
    return render(request, 'users/choose_role.html')

from django.views.decorators.http import require_POST

@require_POST
def send_offer_view(request):

    trip_id = request.POST.get("trip_id")
    ride_request_id = request.POST.get("ride_request_id")

    trip = Trip.objects.get(id=trip_id)
    ride_request = RideRequest.objects.get(id=ride_request_id)

    detour, fare = calculate_detour_and_fare(trip, ride_request)

    #create offer
    RideOffer.objects.create(
        trip=trip,
        ride_request=ride_request,
        proposed_fare=fare,      
        detour_nodes=detour,    
        status="pending"
    )

    return redirect(f"/api/trips/dashboard/{trip.id}/")