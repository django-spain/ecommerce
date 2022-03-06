from datetime import datetime
from django.http import JsonResponse
from django.shortcuts import render
from carts.models import CartItem
from .forms import OrderForm
import datetime
from django.shortcuts import redirect, render
from .models import Order, Payment, OrderProduct
import json
from store.models import Product
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.http import JsonResponse

# Create your views here.
def payments(request):
    if request.method == 'POST':
        body = json.loads(request.body)
        order = Order.objects.get(user=request.user, is_ordered=False, order_number=body['orderID'])
        payment = Payment(
            user = request.user,
            payment_id = body['transID'],
            payment_method = body['payment_method'],
            amount_id = order.order_total,
            status = body['status'],
        )
        payment.save()
        
        order.payment = payment
        order.is_ordered = True
        order.save()
        
        # Mover el carrito a la los item de la linea de la orden
        cart_items = CartItem.objects.filter(user=request.user)
        
        for item in cart_items:
            # Almacenamos el producto
            orderproduct = OrderProduct()
            orderproduct.order_id = order.id
            orderproduct.payment = payment
            orderproduct.user_id = request.user.id
            orderproduct.product_id = item.product_id
            orderproduct.quantity = item.quantity
            orderproduct.product_price = item.product.price
            orderproduct.ordered = True
            orderproduct.save()
            
            # Grabamos las variantes
            cart_item = CartItem.objects.get(id=item.id)
            product_variation = cart_item.variations.all()
            orderproduct = OrderProduct.objects.get(id=orderproduct.id)
            orderproduct.variation.set(product_variation)
            orderproduct.save()
            
            # Rebajamos el stock
            product = Product.objects.get(id=item.product_id)
            product.stock -= item.quantity
            product.save()
            
        # Limpiamos el carro
        CartItem.objects.filter(user=request.user).delete()
        
        
        # Enviar un email de confirmacion.
        mail_subject = 'Gracias por tu compra'
        body = render_to_string('orders/order_recieved_email.html', {
            'user' : request.user,
            'order' : order
        })
        
        """
        to_email = request.user.email
        send_email = EmailMessage(mail_subject, body, to=[to_email])
        send_email.send()
        """
            
            
        data = {
            'order_number' : order.order_number,
            'transID' : payment.payment_id
        }
        
        return JsonResponse(data)



def place_order(request, total=0, quantity=0):
    current_user = request.user
    cart_items = CartItem.objects.filter(user=current_user)
    cart_count = cart_items.count()
    
    if cart_count <= 0:
        return redirect('store')
    
    grand_total = 0
    tax = 0
    
    for cart_item in cart_items:
        total  += (cart_item.product.price * cart_item.quantity)
        quantity += cart_item.quantity
        
    tax = (2*total)/100
    grand_total = total + tax
    
    if request.method == 'POST':
        form = OrderForm(request.POST)
        
        if form.is_valid():
            data = Order()
            data.user = current_user
            data.first_name = form.cleaned_data['first_name']
            data.last_name = form.cleaned_data['last_name']
            data.phone = form.cleaned_data['phone']
            data.email = form.cleaned_data['email']
            data.addres_line_1 = form.cleaned_data['addres_line_1']
            data.addres_line_2 = form.cleaned_data['addres_line_2']
            data.country = form.cleaned_data['country']
            data.state = form.cleaned_data['state']
            data.city = form.cleaned_data['city']
            data.order_note = form.cleaned_data['order_note']
            data.order_total = grand_total
            data.tax = tax
            data.ip = request.META.get('REMOTE_ADDR')
            data.save()
            
            yr = int(datetime.date.today().strftime('%Y'))
            mt = int(datetime.date.today().strftime('%m'))
            dt = int(datetime.date.today().strftime('%d'))
            d = datetime.date(yr,mt,dt)
            current_date = d.strftime("%Y%m%d")
            # 20220102
            order_number = current_date + str(data.id)
            data.order_number = order_number
            data.save()
            
            order = Order.objects.get(user=current_user, is_ordered=False, order_number=order_number)
            context = {
                'order' : order,
                'cart_items' : cart_items,
                'total' : total,
                'tax' : tax,
                'grand_total' : grand_total, 
                'clear_grand_total' : str(grand_total).replace(",", ".")
            }
            
            
            return render(request, 'orders/payments.html', context)
        
    else:
        return redirect('checkout')
    
    
def order_complete(request):
    order_number = request.GET.get('order_number')
    transID = request.GET.get('payment_id')
    
    try:
        order = Order.objects.get(order_number=order_number, is_ordered=True)
        ordered_products = OrderProduct.objects.filter(order_id=order.id)
        
        subtotal = 0
        for i in ordered_products:
            subtotal += i.product_price * i.quantity
        
        payment = Payment.objects.get(payment_id=transID)
        
        context = {
            'order' : order,
            'ordered_products' : ordered_products,
            'order_number' : order.order_number,
            'transID' : payment.payment_id,
            'payment' : payment,
            'subtotal' : subtotal,
        }
        return render(request, 'orders/order_complete.html', context)

    except Exception as e:
        print(e)
        return redirect('home')
    

