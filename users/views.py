from django.contrib.auth import authenticate
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from .serializers import UserSerializer
from rest_framework.permissions import IsAuthenticated
from .models import Node, Edge, Trip
from .serializers import NodeSerializer, EdgeSerializer, TripSerializer

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
    
