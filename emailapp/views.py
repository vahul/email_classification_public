import os
import base64
import pytz
from datetime import datetime
from django.core.paginator import Paginator
from django.shortcuts import render, redirect
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login
from django.http import HttpResponse
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from langchain_groq import ChatGroq
from bs4 import BeautifulSoup
from .models import Email  # Ensure the Email model is imported
import time
import httpx
from django.db.models import Q


# Define SCOPES for Gmail API
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

# List of Groq API keys
groq_api_keys = [
'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',
    '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',  # Default key
    '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'  # Second alternate key
]

# Initialize ChatGroq with the default API key
llm = ChatGroq(
    model="llama-3.1-70b-versatile",
    temperature=0,
    groq_api_key=groq_api_keys[0]
)


def count_tokens(text):
    return len(text.split())


def classify_email(email, retries=3):
    query = f"What class does this email belong to in the classes Finance, Social, News, Health, Promotions, Job Offers? Just give me the name. Email: {email}"

    # Retry mechanism
    for attempt in range(retries):
        try:
            # Try using each Groq API key in the list
            for api_key in groq_api_keys:
                llm = ChatGroq(
                    model="llama-3.1-70b-versatile",
                    temperature=0,
                    groq_api_key=api_key
                )

                response = llm.invoke(query)
                return response.content
        except httpx.HTTPStatusError as e:
            # If rate limit (429) error occurs
            if e.response.status_code == 429:
                print(f"Rate limit hit with key {api_key}, retrying with a different key in {attempt + 1} seconds...")
                time.sleep(attempt + 1)  # Exponential backoff: Increase sleep time with each retry
            else:
                # Raise the error for other types of HTTP errors
                raise e

    return None  # If all retries fail


def summarize(text):
    query = f"Give me the overall summary and mention the key points of the mail {text}. If the mail is empty, say that the mail is empty."
    response = llm.invoke(query)
    return response.content


def get_gmail_service():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    else:
        flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
        creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return build('gmail', 'v1', credentials=creds)

def get_now_emails(service, page_number):
    ist = pytz.timezone('Asia/Kolkata')
    today_midnight = datetime.now(ist).replace(hour=0, minute=0, second=0, microsecond=0)
    query = f"after:{int(today_midnight.timestamp())}"

    try:
        results = service.users().messages().list(userId='me', q=query).execute()
        messages = results.get('messages', [])
        print(len(messages))
        emails = []
        batch_size = 5
        start_index = (page_number - 1) * batch_size  # Correctly calculate start index
        end_index = start_index + batch_size  # Calculate end index

        batch = messages[start_index:end_index]  # Slice the batch based on page number

        for message in batch:
            msg = service.users().messages().get(userId='me', id=message['id']).execute()
            headers = msg.get('payload', {}).get('headers', [])
            email_data = {'sender': 'Unknown', 'subject': 'No Subject', 'body': 'No Content'}

            for header in headers:
                if header['name'] == 'From':
                    email_data['sender'] = header['value']
                elif header['name'] == 'Subject':
                    email_data['subject'] = header['value']

            parts = msg.get('payload', {}).get('parts', [])
            for part in parts:
                if part['mimeType'] == 'text/plain':
                    body_data = part.get('body', {}).get('data', '')
                    if body_data:
                        email_data['body'] = base64.urlsafe_b64decode(body_data).decode('utf-8')
                        break
                elif part['mimeType'] == 'text/html':
                    body_data = part.get('body', {}).get('data', '')
                    if body_data:
                        decoded_body = base64.urlsafe_b64decode(body_data).decode('utf-8')
                        email_data['body'] = BeautifulSoup(decoded_body, 'html.parser').get_text()
                        break

            email_data['body'] = summarize(email_data['body'])
            time.sleep(3)
            email_text =email_data['sender']+" "+  email_data['subject'] + " " + email_data['body']
            print(type(email_text))
            if "oracle" in email_text:
                email_data['classification']="oracle"
            else:
                email_data['classification'] = classify_email(email_text)
            emails.append(email_data)
            if not Email.objects.filter(
                    Q(sender=email_data['sender']) &
                    Q(subject=email_data['subject']) &
                    Q(body=email_data['body'])
            ).exists():
                # If not, create a new entry
                Email.objects.create(
                    sender=email_data['sender'],
                    subject=email_data['subject'],
                    body=email_data['body'],
                    classification=email_data['classification']
                )

        return emails,len(messages)//batch_size
    except Exception as error:
        print(f"Error fetching emails: {error}")
        return []


def get_todays_emails(service, page_number, start_date=None, end_date=None):
    ist = pytz.timezone('Asia/Kolkata')
    today_midnight = datetime.now(ist).replace(hour=0, minute=0, second=0, microsecond=0)
    start_timestamp = int(today_midnight.timestamp()) if not start_date else int(start_date.timestamp())
    end_timestamp = int(today_midnight.timestamp()) if not end_date else int(end_date.timestamp())

    query = f"after:{start_timestamp} before:{end_timestamp}"

    try:
        results = service.users().messages().list(userId='me', q=query).execute()
        messages = results.get('messages', [])
        emails = []
        batch_size = 5
        total_batches = len(messages) // batch_size + (1 if len(messages) % batch_size != 0 else 0)

        # Start processing the emails in the current page
        start_index = (page_number - 1) * batch_size
        end_index = start_index + batch_size
        batch = messages[start_index:end_index]

        batch_emails = []
        for message in batch:
            msg = service.users().messages().get(userId='me', id=message['id']).execute()
            headers = msg.get('payload', {}).get('headers', [])
            email_data = {'sender': 'Unknown', 'subject': 'No Subject', 'body': 'No Content'}

            for header in headers:
                if header['name'] == 'From':
                    email_data['sender'] = header['value']
                elif header['name'] == 'Subject':
                    email_data['subject'] = header['value']

            parts = msg.get('payload', {}).get('parts', [])
            for part in parts:
                if part['mimeType'] == 'text/plain':
                    body_data = part.get('body', {}).get('data', '')
                    if body_data:
                        email_data['body'] = base64.urlsafe_b64decode(body_data).decode('utf-8')
                        break
                elif part['mimeType'] == 'text/html':
                    body_data = part.get('body', {}).get('data', '')
                    if body_data:
                        decoded_body = base64.urlsafe_b64decode(body_data).decode('utf-8')
                        email_data['body'] = BeautifulSoup(decoded_body, 'html.parser').get_text()
                        break

            email_data['body'] = summarize(email_data['body'])
            time.sleep(3)
            email_text =email_data['sender']+" "+ email_data['subject'] + " " + email_data['body']
            print(type(email_text))
            if "oracle" in email_text:
                email_data['classification']="oracle"
            else:
                email_data['classification'] = classify_email(email_text)
            batch_emails.append(email_data)
            if not Email.objects.filter(
                    Q(sender=email_data['sender']) &
                    Q(subject=email_data['subject']) &
                    Q(body=email_data['body'])
            ).exists():
                # If not, create a new entry
                Email.objects.create(
                    sender=email_data['sender'],
                    subject=email_data['subject'],
                    body=email_data['body'],
                    classification=email_data['classification']
                )
        emails.extend(batch_emails)
        print(f"Batch {page_number} processed.")
        time.sleep(3)
        print(len(messages))
        return emails,len(messages)//batch_size

    except Exception as error:
        print(f"Error fetching emails: {error}")
        return []

def login_view(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('home')
    else:
        form = UserCreationForm()
    return render(request, 'emailapp/login.html', {'form': form})


def signup_view(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('home')
    else:
        form = UserCreationForm()
    return render(request, 'emailapp/signup.html', {'form': form})


def home_view(request):
    return render(request, 'emailapp/index.html')


def process_email_batch(email_batch):
    """
    Processes a batch of emails, classifies and summarizes them, and saves to the database.
    """
    for email in email_batch:
        email_text = email['subject'] + " " + email['body']
        if "oracle" in email:
            print(email)
            email['classification'] = "oracle"
        else:
            email['classification'] = classify_email(email_text)
        email['body'] = summarize(email['body'])

        # Save each email to the database
        Email.objects.create(
            sender=email['sender'],
            subject=email['subject'],
            body=email['body'],
            classification=email['classification']
        )


def classify_view(request):
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    start_date = datetime.fromisoformat(start_date) if start_date else None
    end_date = datetime.fromisoformat(end_date) if end_date else None
    page_number = request.GET.get('page')
    if page_number==None:
        page_number=1
    else:
        page_number=int(page_number)
    service = get_gmail_service()
    if start_date == None and end_date == None:
        emails,count = get_now_emails(service,page_number)
    else:
        emails,count = get_todays_emails(service, page_number,start_date, end_date)
    # Paginator
    paginator = Paginator(emails*count, 5)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Save emails to the database in batches of 5
    # email_batch = []
    # for email in page_obj.object_list:
    #     email_batch.append(email)
    #
    #     # Process only 5 emails at a time
    #     if len(email_batch) == 5:
    #         process_email_batch(email_batch)
    #         email_batch = []  # Clear the batch after processing
    #
    # # If there are any remaining emails less than 5 after the loop, process them
    # if email_batch:
    #     process_email_batch(email_batch)

    return render(request, 'emailapp/allmails.html', {'emails': page_obj})


def categorized_emails_view(request, category):
    emails = Email.objects.filter(classification__icontains=category)
    paginator = Paginator(emails, 5)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, f'emailapp/{category}_emails.html', {'emails': page_obj})


def finance_emails(request):
    return categorized_emails_view(request, 'finance')


def social_emails(request):
    return categorized_emails_view(request, 'social')


def news_emails(request):
    return categorized_emails_view(request, 'news')


def health_emails(request):
    return categorized_emails_view(request, 'health')


def promotions_emails(request):
    return categorized_emails_view(request, 'promotions')


def job_emails(request):
    return categorized_emails_view(request, 'job Offers')
def oracle_emails(request):
    return categorized_emails_view(request, 'oracle')
