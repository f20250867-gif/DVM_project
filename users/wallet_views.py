from rest_framework.views import APIView, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from .models import Transaction

class WalletTopUpView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        amount = request.data.get('amount')
        
        try:
            amount = float(amount)
            if amount <= 0:
                raise ValueError
        except (TypeError, ValueError):
            return Response({"error": "Please provide a valid positive amount."}, status=status.HTTP_400_BAD_REQUEST)

        user = request.user
        
        # Update wallet balance and create transaction record atomically
        with transaction.atomic():
            user.wallet_balance += amount
            user.save()
            
            Transaction.objects.create(
                user=user,
                amount=amount,
                transaction_type='topup'
            )
            
        return Response({
            "message": "Wallet topped up successfully.",
            "new_balance": user.wallet_balance
        }, status=status.HTTP_200_OK)