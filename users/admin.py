from django.contrib import admin
from .models import User
from .models import Node, Edge, Trip, RideRequest

# Register your models here.

admin.site.register(User)
admin.site.register(Node)
admin.site.register(Edge)
admin.site.register(Trip)
admin.site.register(RideRequest)