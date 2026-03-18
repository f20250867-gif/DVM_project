from django.contrib import admin
from .models import User
from .models import Node, Edge, Trip, RideRequest,SystemSettings, RideOffer
from users import models

# Register your models here.
admin.site.register(User)

@admin.register(Node)
class NodeAdmin(admin.ModelAdmin):  
    list_display = ('id', 'name', 'latitude', 'longitude')
    search_fields = ('name',)

    
    

@admin.register(Edge)
class EdgeAdmin(admin.ModelAdmin):
    # Allows admin to Add/Remove edges easily
    list_display = ('id', 'from_node', 'to_node', 'distance')
    list_filter = ('from_node', 'to_node')

    def __str__(self):
        return self.list_

@admin.register(Trip)
class TripAdmin(admin.ModelAdmin):
    # Allows admin to view all active trips on the network
    list_display = ('id', 'driver', 'start_node', 'end_node', 'current_node', 'available_seats')
    list_filter = ('driver',)

@admin.register(RideRequest)
class RideRequestAdmin(admin.ModelAdmin):
    list_display = ('id', 'passenger', 'pickup_node', 'drop_node', 'status')
    list_filter = ('status',)

@admin.register(SystemSettings)
class SystemSettingsAdmin(admin.ModelAdmin):
    list_display = ('is_carpool_active',)

@admin.register(RideOffer)
class RideOfferAdmin(admin.ModelAdmin):
    list_display = ('id', 'trip', 'ride_request', 'status')
    list_filter = ('status',)