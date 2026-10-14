
from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("cart/", views.cart_view, name="cart"),
    path(
        "add-to-cart/<int:product_id>/",
        views.add_to_cart,
        name="add_to_cart",
    ),
    path(
        "remove-from-cart/<int:product_id>/",
        views.remove_from_cart,
        name="remove_from_cart",
    ),
    path(
        "update-cart/<int:product_id>/",
        views.update_cart_quantity,
        name="update_cart_quantity",
    ),


    path("checkout/", views.checkout, name="checkout"),
path(
    "order-success/<int:order_id>/",
    views.order_success,
    name="order_success"
),

path("my-orders/", views.my_orders, name="my_orders"),
    path("", views.home, name="home"),
    path("signup/", views.signup_view, name="signup"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),

    
path("my-account/", views.my_account, name="my_account"),

]

