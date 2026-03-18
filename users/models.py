from django.db import models
from django.contrib.auth.models import AbstractUser

# Create your models here.

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

    def __str__(self):
        return self.username

class Node(models.Model):

    name = models.CharField(max_length=100)
    latitude = models.FloatField()
    longitude = models.FloatField()

#Edge Model
class Edge(models.Model):

    from_node = models.ForeignKey(Node, on_delete=models.CASCADE, related_name="from_edges")
    to_node = models.ForeignKey(Node, on_delete=models.CASCADE, related_name="to_edges")

    distance = models.FloatField()

    class Meta:
        unique_together = ("from_node", "to_node")
    
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