from django.contrib.auth import authenticate
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from .serializers import UserSerializer
from rest_framework.permissions import IsAuthenticated
from .models import Node, Edge, Trip
from .serializers import NodeSerializer, EdgeSerializer, TripSerializer
from .utils import shortest_path
from .models import RideRequest
from .serializers import RideRequestSerializer
from .utils import find_matching_trips
from django.db import transaction
from django.shortcuts import get_object_or_404


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
        })


class RegisterView(APIView):

    def post(self, request):
        serializer = UserSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            refresh = RefreshToken.for_user(user)
            return Response({
                "user": serializer.data,
                "refresh": str(refresh),
                "access": str(refresh.access_token),
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

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

    def get(self, request):

        trips = Trip.objects.all()
        serializer = TripSerializer(trips, many=True)

        return Response(serializer.data)


    def post(self, request):

        serializer = TripSerializer(data=request.data)

        if serializer.is_valid():
            serializer.save(driver=request.user)

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

    permission_classes = [IsAuthenticated]

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

        trip.current_node_id = node_id
        trip.save()

        return Response({
            "message": "Location updated",
            "current_node": node_id
        })

