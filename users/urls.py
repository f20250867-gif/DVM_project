from django.urls import path
from .views import RegisterView, LoginView, MeView
from .views import NodeView, EdgeView, TripView
from rest_framework.views import APIView
from .views import RouteView
from .views import RideRequestView,CancelTripView, UpdateLocationView


urlpatterns = [
    path('register/', RegisterView.as_view()),
    path('login/', LoginView.as_view()),
    path('me/', MeView.as_view()),
    path('nodes/', NodeView.as_view()),
    path('edges/', EdgeView.as_view()), 
    path('trips/', TripView.as_view()),
    path('route/', RouteView.as_view()),
    path("ride-request/", RideRequestView.as_view()),
    path("trips/cancel/", CancelTripView.as_view()),
    path("trips/update-location/", UpdateLocationView.as_view()),

]