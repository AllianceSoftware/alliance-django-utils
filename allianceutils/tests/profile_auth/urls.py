from django.conf.urls import url

from .views import LoginRequiredView

app_name = 'profile_auth'

urlpatterns = [
    url(r'^protected/$', LoginRequiredView.as_view(), name='login_required')
]
