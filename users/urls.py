from django.urls import include, path
from .views import RegisterView, LoginView, MeView, driver_dashboard_ssr, passenger_accept_offer, passenger_cancel_request, passenger_accept_offer, passenger_dashboard_ssr, passenger_offers_ssr
from .views import NodeView, EdgeView, TripView
from rest_framework.views import APIView
from .views import RouteView
from .views import RideRequestView,CancelTripView, UpdateLocationView,AcceptOfferView,DriverRequestsAPIView,MakeOfferView, driver_dashboard_ssr


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
    path('trips/<int:trip_id>/requests/', DriverRequestsAPIView.as_view(), name='driver-requests-api'),
    path('dashboard/<int:trip_id>/', driver_dashboard_ssr, name='driver-dashboard-ssr'),
    path("trips/make-offer/", MakeOfferView.as_view(), name="make-offer"),
    path("trips/dashboard/<int:trip_id>/", driver_dashboard_ssr, name="driver-dashboard"),
    path('offers/<int:offer_id>/accept/', AcceptOfferView.as_view(), name='accept-offer'),
    path('api-auth/', include('rest_framework.urls')),
    path('passenger/dashboard/', passenger_dashboard_ssr, name='passenger-dashboard'),
    path('passenger/request/<int:request_id>/', passenger_offers_ssr, name='passenger-offers'),
    path('passenger/request/<int:request_id>/cancel/', passenger_cancel_request, name='passenger-cancel'),
    path('passenger/offer/<int:offer_id>/accept/', passenger_accept_offer, name='passenger-accept-offer'),
]