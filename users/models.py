from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    
    ROLE_CHOICES = [
        ('driver', 'Driver'),
        ('passenger', 'Passenger'),
    ]

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default='passenger'
    )

    wallet_balance = models.FloatField(default=0.0)

    def __str__(self):
        return self.username

class Node(models.Model):

    name = models.CharField(max_length=100)
    latitude = models.FloatField()
    longitude = models.FloatField()

    def __str__(self):
        return self.name

#Edge Model
class Edge(models.Model):

    from_node = models.ForeignKey(Node, on_delete=models.CASCADE, related_name="from_edges")
    to_node = models.ForeignKey(Node, on_delete=models.CASCADE, related_name="to_edges")

    distance = models.FloatField()

    class Meta:
        unique_together = ("from_node", "to_node")

    def __str__(self):
        return f"{self.from_node} -> {self.to_node} ({self.distance} km)"
    
#Trip Model
class Trip(models.Model):

    driver = models.ForeignKey(
        User,
        on_delete=models.CASCADE
    )

    start_node = models.ForeignKey(
        Node,
        on_delete=models.CASCADE,
        related_name="trip_start"
    )

    end_node = models.ForeignKey(
        Node,
        on_delete=models.CASCADE,
        related_name="trip_end"
    )

    current_node = models.ForeignKey(
        Node,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="trip_current"
    )
    route = models.JSONField(null=True, blank=True)#storing the route
    visited_nodes = models.JSONField(default=list, blank=True)#to keep track of visited nodes during the trip

    max_passengers = models.IntegerField()

    available_seats = models.IntegerField()

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.driver} {self.start_node}->{self.end_node}"
    
#Ride Request Model
class RideRequest(models.Model):

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("matched", "Matched"),
        ("completed", "Completed"),
    ]

    passenger = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="ride_requests"
    )

    pickup_node = models.ForeignKey(
        Node,
        on_delete=models.CASCADE,
        related_name="pickup_requests"
    )

    drop_node = models.ForeignKey(
        Node,
        on_delete=models.CASCADE,
        related_name="drop_requests"
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.passenger} {self.pickup_node}->{self.drop_node}"



class RideOffer(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),     
        ("accepted", "Accepted"),  
        ("rejected", "Rejected"),  
    ]

    ride_request = models.ForeignKey(RideRequest, on_delete=models.CASCADE, related_name="offers")
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name="trip_offers")
    
    proposed_fare = models.FloatField(default=0.0)
    detour_nodes = models.IntegerField(default=0)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # A driver can only make one offer per request
        unique_together = ("ride_request", "trip")

    def __str__(self):
        return f"Offer by {self.trip.driver.username} for Request {self.ride_request.id}"
    
class SystemSettings(models.Model):
    is_carpool_active = models.BooleanField(
        default=True, 
        help_text="Toggle to suspend or re-enable the carpooling service globally."
    )

    class Meta:
        verbose_name_plural = "System Settings"

    def save(self, *args, **kwargs):
        if not self.pk and SystemSettings.objects.exists():
            return
        super().save(*args, **kwargs)

    def __str__(self):
        status = "Active" if self.is_carpool_active else "Suspended"
        return f"Carpool Service Status: {status}"
    


class Transaction(models.Model):
    TRANSACTION_TYPES = [
        ('topup', 'Top-up'),
        ('deduction', 'Fare Deduction'),
        ('earning', 'Driver Earning'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="transactions")
    amount = models.FloatField()
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)

    trip = models.ForeignKey('Trip', on_delete=models.SET_NULL, null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} | {self.get_transaction_type_display()} | ${self.amount}"