
from django.db import transaction
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.views.decorators.http import require_POST
from django.shortcuts import render, redirect, get_object_or_404

from .models import Product, Order, OrderItem


@login_required
def my_account(request):
    return render(request, "store/my_account.html", {
        "account_user": request.user,
    })

# HOME PAGE
def home(request):
    products = Product.objects.all()
    cart = request.session.get("cart", {})
    cart_count = sum(int(q) for q in cart.values())

    return render(request, "store/home.html", {
        "products": products,
        "cart_count": cart_count,
    })


# ADD PRODUCT TO CART
@require_POST
def add_to_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    cart = request.session.get("cart", {})
    product_id = str(product.id)

    try:
        quantity = int(cart.get(product_id, 0))
    except (TypeError, ValueError):
        quantity = 0

    if quantity < product.stock:
        cart[product_id] = quantity + 1
        request.session["cart"] = cart
        messages.success(
            request, f"{product.name} added to your cart!"
        )
    else:
        messages.warning(
            request, "Sorry, this product is out of stock."
        )

    return redirect(request.META.get("HTTP_REFERER", "/"))


# CART PAGE
def cart_view(request):
    cart = request.session.get("cart", {})
    cart_items = []
    total = 0
    cart_count = 0

    for product_id, quantity in cart.items():
        try:
            product = Product.objects.get(id=int(product_id))
            quantity = int(quantity)
        except (Product.DoesNotExist, ValueError, TypeError):
            continue

        if quantity <= 0:
            continue

        subtotal = product.price * quantity
        total += subtotal
        cart_count += quantity

        cart_items.append({
            "product": product,
            "quantity": quantity,
            "subtotal": subtotal,
        })

    return render(request, "store/cart.html", {
        "cart_items": cart_items,
        "total": total,
        "cart_count": cart_count,
    })


# REMOVE PRODUCT FROM CART
@require_POST
def remove_from_cart(request, product_id):
    cart = request.session.get("cart", {})
    cart.pop(str(product_id), None)
    request.session["cart"] = cart

    return redirect("cart")


# UPDATE CART QUANTITY
@require_POST
def update_cart_quantity(request, product_id):
    cart = request.session.get("cart", {})
    product = get_object_or_404(Product, id=product_id)

    try:
        quantity = int(request.POST.get("quantity", 1))
    except (TypeError, ValueError):
        quantity = 1

    if quantity <= 0:
        cart.pop(str(product_id), None)

    elif quantity <= product.stock:
        cart[str(product_id)] = quantity

    else:
        messages.warning(
            request,
            f"Only {product.stock} items are available."
        )

    request.session["cart"] = cart
    return redirect("cart")


# CHECKOUT PAGE
@login_required
def checkout(request):
    cart = request.session.get("cart", {})
    cart_items = []
    total = 0

    for product_id, quantity in cart.items():
        try:
            product = Product.objects.get(id=int(product_id))
            quantity = int(quantity)
        except (Product.DoesNotExist, ValueError, TypeError):
            continue

        if quantity <= 0:
            continue

        subtotal = product.price * quantity
        total += subtotal

        cart_items.append({
            "product": product,
            "quantity": quantity,
            "subtotal": subtotal,
        })

    if not cart_items:
        messages.warning(request, "Your cart is empty.")
        return redirect("cart")

    if request.method == "POST":
        full_name = request.POST.get("full_name", "").strip()
        mobile = request.POST.get("mobile", "").strip()
        address = request.POST.get("address", "").strip()
        city = request.POST.get("city", "").strip()
        state = request.POST.get("state", "").strip()
        pincode = request.POST.get("pincode", "").strip()
        payment_method = request.POST.get("payment_method", "COD")

        if payment_method not in ("COD", "UPI"):
            messages.error(
                request, "Please select a valid payment method."
            )

        elif not all([
            full_name, mobile, address, city, state, pincode
        ]):
            messages.error(
                request, "Please fill in all delivery details."
            )

        elif not mobile.isdigit() or len(mobile) != 10:
            messages.error(
                request, "Enter a valid 10-digit mobile number."
            )

        elif not pincode.isdigit() or len(pincode) != 6:
            messages.error(
                request, "Enter a valid 6-digit PIN code."
            )

        else:
            try:
                with transaction.atomic():
                    products = {}
                    verified_total = 0

                    # Verify current stock and prices
                    for item in cart_items:
                        product = Product.objects.select_for_update().get(
                            id=item["product"].id
                        )

                        if product.stock < item["quantity"]:
                            raise ValueError(
                                f"Only {product.stock} units of "
                                f"{product.name} are available."
                            )

                        products[product.id] = product
                        verified_total += (
                            product.price * item["quantity"]
                        )

                    # Save order against logged-in customer
                    order = Order.objects.create(
                        user=request.user,
                        full_name=full_name,
                        mobile=mobile,
                        address=address,
                        city=city,
                        state=state,
                        pincode=pincode,
                        total_amount=verified_total,
                        payment_method=payment_method,
                        payment_status="Pending",
                    )

                    # Save order items and reduce stock
                    for item in cart_items:
                        product = products[item["product"].id]

                        OrderItem.objects.create(
                            order=order,
                            product=product,
                            quantity=item["quantity"],
                            price=product.price,
                        )

                        product.stock -= item["quantity"]
                        product.save(update_fields=["stock"])

                request.session["cart"] = {}
                request.session["last_order_id"] = order.id

                return redirect(
                    "order_success",
                    order_id=order.id
                )

            except ValueError as error:
                messages.error(request, str(error))

            except Product.DoesNotExist:
                messages.error(
                    request,
                    "A product is no longer available. "
                    "Please review your cart."
                )

    return render(request, "store/checkout.html", {
        "cart_items": cart_items,
        "total": total,
        "cart_count": sum(
            item["quantity"] for item in cart_items
        ),
    })


# ORDER SUCCESS PAGE
@login_required
def order_success(request, order_id):
    order = get_object_or_404(
        Order,
        id=order_id,
        user=request.user
    )

    return render(request, "store/order_success.html", {
        "order": order,
    })


# MY ORDERS PAGE - ONLY LOGGED-IN USER'S ORDERS
@login_required
def my_orders(request):
    orders = Order.objects.filter(
        user=request.user
    ).order_by("-created_at")

    return render(request, "store/my_orders.html", {
        "orders": orders,
    })


# SIGNUP PAGE
def signup_view(request):
    if request.user.is_authenticated:
        return redirect("home")

    if request.method == "POST":
        form = UserCreationForm(request.POST)

        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(
                request, "Account created successfully!"
            )
            return redirect("home")
    else:
        form = UserCreationForm()

    return render(request, "store/signup.html", {
        "form": form,
    })


# LOGIN PAGE
def login_view(request):
    if request.user.is_authenticated:
        return redirect("home")

    if request.method == "POST":
        form = AuthenticationForm(
            request, data=request.POST
        )

        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect("home")
    else:
        form = AuthenticationForm()

    return render(request, "store/login.html", {
        "form": form,
    })


# LOGOUT
def logout_view(request):
    if request.method == "POST":
        logout(request)

    return redirect("home")
