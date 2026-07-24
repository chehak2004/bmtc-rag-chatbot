"""
seed_content.py
---------------
Fallback / bootstrap knowledge base content for BMTC (BookMyTestCenter).

Why this exists:
Live web scraping depends on network access to bookmytestcenter.com and its
subdomains, which may be blocked or rate-limited in some deployment
environments (e.g. sandboxed CI, restricted egress). To guarantee the RAG
pipeline always has *something* to index and the chatbot is demoable out of
the box, we ship a small set of hand-written, clearly-labeled seed documents
covering the topics the assistant is expected to answer (registration, portal
usage, FAQs). These are used only if `scraper.py` returns zero pages for a
domain, or if `python ingestion/scraper.py --seed-only` is run explicitly.

IMPORTANT: Replace/expand this content with real scraped or officially
provided text before production launch. Treat this as placeholder scaffolding,
not verified BMTC policy.
"""

SEED_PAGES = [
    {
        "url": "https://bookmytestcenter.com/",
        "title": "BookMyTestCenter - Home",
        "text": (
            "BookMyTestCenter (BMTC) is an online platform that connects candidates who need to take "
            "certification or licensing exams with certified test centers. Through the BMTC website, "
            "users can search for available test centers, compare schedules, book an exam slot, and "
            "manage their bookings online. BMTC serves three types of users: candidates who book exams, "
            "test center administrators who manage center availability, and client organizations that "
            "administer exams to their own candidates. Support is available through the Help Center and "
            "the contact form on the main website."
        ),
        "source_domain": "bookmytestcenter.com",
    },
    {
        "url": "https://bookmytestcenter.com/faq",
        "title": "BookMyTestCenter - Frequently Asked Questions",
        "text": (
            "How do I create an account on BookMyTestCenter? Click Sign Up on the homepage, enter your "
            "name, email address, and phone number, then verify your email using the OTP sent to your inbox. "
            "How do I book a test slot? After logging in, search for your exam by name or category, choose a "
            "test center from the list of available centers, select an open date and time slot, and confirm "
            "the booking. You will receive a confirmation email with your booking reference number. "
            "Can I reschedule or cancel a booking? Yes, go to My Bookings, select the booking you want to "
            "change, and choose Reschedule or Cancel. Rescheduling is subject to the test center's rescheduling "
            "policy and may be allowed only up to a certain number of hours before the exam. "
            "What payment methods are supported? BMTC supports credit cards, debit cards, UPI, and net banking "
            "for exam fee payments. "
            "What if I forget my password? Click Forgot Password on the login page and follow the instructions "
            "sent to your registered email to reset it. "
            "Who do I contact for support? Use the Contact Us page on bookmytestcenter.com or email the support "
            "team listed there."
        ),
        "source_domain": "bookmytestcenter.com",
    },
    {
        "url": "https://center.bookmytestcenter.com/",
        "title": "BMTC Center Portal - Overview",
        "text": (
            "The Center Portal (center.bookmytestcenter.com) is where test center administrators manage their "
            "test center's presence on BookMyTestCenter. How do I register my test center? Visit the Center "
            "Portal, click Register as a Test Center, and fill in your center's name, address, contact details, "
            "available exam categories, and capacity. After submission, the BMTC verification team reviews the "
            "application, which typically takes 2-3 business days, and you will receive an approval email once "
            "your center is verified. "
            "How do I manage seat availability? Log in to the Center Portal, go to the Availability Calendar, "
            "and set open slots, block dates, or update seat capacity for each exam type. "
            "How do I view bookings made at my center? The Bookings tab in the Center Portal lists all upcoming "
            "and past candidate bookings, along with candidate details and payment status. "
            "How do I update my center profile or documents? Go to Center Settings to update contact information, "
            "upload updated compliance documents, or change operating hours. "
            "Can multiple staff members access the Center Portal? Yes, the primary administrator can invite "
            "additional staff accounts with restricted permissions from the Team Management section."
        ),
        "source_domain": "center.bookmytestcenter.com",
    },
    {
        "url": "https://clients.bookmytestcenter.com/",
        "title": "BMTC Client Portal - Overview",
        "text": (
            "The Client Portal (clients.bookmytestcenter.com) is designed for organizations and institutions "
            "that need to administer exams to their own candidates through the BMTC network. "
            "How do I register as a client organization? Visit the Client Portal and click Register Organization. "
            "Provide your organization name, business registration details, and the type of exams you plan to "
            "administer. Your account will be activated after BMTC's onboarding team verifies the submitted "
            "details. "
            "How do I bulk-upload candidates? Once logged in, go to Candidate Management, click Bulk Upload, "
            "and use the provided CSV template to add multiple candidates at once. "
            "How do I generate exam reports? The Reports section of the Client Portal allows you to download "
            "candidate performance, attendance, and booking reports in CSV or PDF format. "
            "How do I set up custom exam schedules for my organization? Use the Exam Scheduling tool in the "
            "Client Portal to define exam windows, assign eligible test centers, and set candidate eligibility "
            "rules. "
            "Who approves client organization registrations? BMTC's client onboarding team reviews and approves "
            "new client organization sign-ups, typically within 2-3 business days."
        ),
        "source_domain": "clients.bookmytestcenter.com",
    },
    {
        "url": "https://bookmytestcenter.com/registration-guide",
        "title": "BookMyTestCenter - Registration Guide (Candidates)",
        "text": (
            "To register as a candidate on BookMyTestCenter: 1) Go to bookmytestcenter.com and click Sign Up. "
            "2) Enter your full name, email address, mobile number, and create a password. 3) Verify your email "
            "using the one-time password (OTP) sent to your inbox. 4) Complete your profile with your date of "
            "birth and government ID details, which may be required for exam eligibility verification. 5) Once "
            "your profile is complete, you can search for exams, select a test center, and book a slot. "
            "If you are registering a test center instead of a candidate account, use the Center Portal at "
            "center.bookmytestcenter.com. If you are registering a client organization, use the Client Portal "
            "at clients.bookmytestcenter.com."
        ),
        "source_domain": "bookmytestcenter.com",
    },
]


def get_seed_pages():
    return SEED_PAGES
