from django.urls import path
from emailapp import views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('signup/', views.signup_view, name='signup'),
    path('', views.home_view, name='home'),
    path('classify/', views.classify_view, name='classify'),
    path('emails/', views.classify_view, name='allmails'),  # This now supports date filtering and pagination
    path('emails/page/<int:page>/', views.classify_view, name='allmails_paginated'),  # For pagination
    path('finance/', views.categorized_emails_view, {'category': 'finance'}, name='finance_emails'),
    path('finance/page/<int:page>/', views.categorized_emails_view, {'category': 'finance'}, name='finance_emails_paginated'),
    path('social/', views.categorized_emails_view, {'category': 'social'}, name='social_emails'),
    path('social/page/<int:page>/', views.categorized_emails_view, {'category': 'social'}, name='social_emails_paginated'),
    path('news/', views.categorized_emails_view, {'category': 'news'}, name='news_emails'),
    path('news/page/<int:page>/', views.categorized_emails_view, {'category': 'news'}, name='news_emails_paginated'),
    path('health/', views.categorized_emails_view, {'category': 'health'}, name='health_emails'),
    path('health/page/<int:page>/', views.categorized_emails_view, {'category': 'health'}, name='health_emails_paginated'),
    path('promotions/', views.categorized_emails_view, {'category': 'promotions'}, name='promotions_emails'),
    path('promotions/page/<int:page>/', views.categorized_emails_view, {'category': 'promotions'}, name='promotions_emails_paginated'),
    path('job/', views.categorized_emails_view, {'category': 'job'}, name='job_emails'),
    path('job/page/<int:page>/', views.categorized_emails_view, {'category': 'job'}, name='job_emails_paginated'),
    path('oracle/', views.categorized_emails_view, {'category': 'oracle'}, name='oracle_emails'),
    path('oracle/page/<int:page>/', views.categorized_emails_view, {'category': 'oracle'}, name='oracle_emails_paginated'),

]
