from django.urls import path
from . import views

app_name = 'reclamations'

urlpatterns = [
    path('', views.ReclamationListView.as_view(), name='liste'),
    path('nouvelle/', views.ReclamationCreateView.as_view(), name='creer'),
    path('<int:pk>/', views.ReclamationDetailView.as_view(), name='detail'),
    path('<int:pk>/modifier/', views.ReclamationUpdateView.as_view(), name='modifier'),
    path('<int:pk>/supprimer/', views.ReclamationDeleteView.as_view(), name='supprimer'),
]