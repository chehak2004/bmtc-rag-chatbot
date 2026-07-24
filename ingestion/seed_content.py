"""
seed_content.py
---------------
Curated, VERIFIED knowledge base content for BMTC (BookMyTestCenter).

Provenance: this content was extracted directly from the live public pages
at bookmytestcenter.com, center.bookmytestcenter.com, and
clients.bookmytestcenter.com (fetched 2026-07-24), including registration
form flows that a simple HTML scraper often can't reconstruct because they're
rendered step-by-step by client-side JavaScript. It is NOT guesswork or
plausible-sounding filler — every fact below was read directly off the real
site. If the real site changes, this file will go stale and should be
re-verified and updated.

This content is always merged in alongside whatever scraper.py finds live
(see scraper.py's run_scraper()), specifically to fill gaps where real
product/registration-flow content is rendered client-side or otherwise
missed by the basic crawler, while still keeping the main FAQ/marketing
content that the live scrape does successfully capture.
"""

SEED_PAGES = [
    {
        "url": "https://bookmytestcenter.com/",
        "title": "BookMyTestCenter - Company Overview",
        "text": (
            "BookMyTestCenter (BMTC) is a product of Testpan India Pvt Ltd, a provider of "
            "examination delivery and infrastructure services in the public and private sectors. "
            "Testpan India was founded in early 2016 and is recognized as a Startup Company by the "
            "Department for Promotion of Industry and Internal Trade (DPIIT). "
            "BMTC is described as India's first one-stop digital solution for examination center "
            "bookings and infrastructure support services. It streamlines the process of finding, "
            "connecting with, and booking test centers for assessment companies and examination "
            "centers through an automated booking system. "
            "The platform serves three types of users, each with their own portal: candidates and "
            "test centers use the Center Portal (center.bookmytestcenter.com) to register and manage "
            "a test center; assessment companies and other client organizations use the Client Portal "
            "(clients.bookmytestcenter.com) to register their organization; a separate Manpower portal "
            "exists at manpowerx.co.in for manpower vendor registration and login. "
            "BMTC's booking features include simplified search of test centers based on location, "
            "capacity, and specialties; secure communication between assessment companies and test "
            "centers; effortless booking that eliminates manual processes and paperwork; and "
            "streamlined management of examination delivery, scheduling, communication, and reporting. "
            "The mobile app additionally offers center management (add/remove/edit center details), "
            "calendar access to check center availability, real-time notifications for booking "
            "confirmations, and a live news feed of assessment industry updates. "
            "BMTC can be contacted at info@testpanindia.com or info@bookmytestcenter.com, and its "
            "corporate office is located in Nangal Raya, New Delhi, India."
        ),
        "source_domain": "bookmytestcenter.com",
    },
    {
        "url": "https://bookmytestcenter.com/#FAQsection",
        "title": "BookMyTestCenter - Frequently Asked Questions (verified from live site)",
        "text": (
            "How does a test center receive bookings? Assessment company clients send their test "
            "requirements to BMTC, and based on the general and technical requirements of the exam, "
            "BMTC routes those requests to matching test centers. The test center then confirms "
            "availability and requirements, and BMTC completes the booking. "
            "How much time does it take to get started with the web portal? Getting started usually "
            "takes 1 to 3 working days after documentation is completed. "
            "Who do I get in touch with if I get stuck or if there is an issue? Every registered user "
            "is assigned a support manager who can be contacted by phone or email. "
            "I am a company — how do I actually send test requirements to BMTC? Test requirements can "
            "be sent through the company (Client) portal, or by directly contacting BMTC's sales or "
            "support team. "
            "Is there a common portal for Assessment Companies and Test Centers? Yes, BMTC offers a "
            "unified platform architecture that connects both assessment companies and test centers, "
            "though assessment companies and test centers use separate portals (Client Portal and "
            "Center Portal respectively) to manage their own accounts."
        ),
        "source_domain": "bookmytestcenter.com",
    },
    {
        "url": "https://center.bookmytestcenter.com/",
        "title": "BMTC Center Portal - Verified Registration Flow (test centers)",
        "text": (
            "The Center Portal (center.bookmytestcenter.com) is where a test center creates an "
            "account and builds its center profile to receive exam bookings. The real registration "
            "flow, as implemented on the live site, is: "
            "Step 1 - Sign up: provide your name, phone number, and agree to the Privacy Policy and "
            "Terms & Conditions. "
            "Step 2 - Verify your phone number using a 6-digit OTP sent by SMS. "
            "Step 3 - Set up a 4-digit M-Pin, which is then used to log in going forward (instead of "
            "a traditional password). "
            "Step 4 - Complete the Center Profile, which has four sections: "
            "(1) Center details - center name, description, center type (Online, Offline, or Both), "
            "postal address, latitude/longitude, uploaded photos (center logo, entrance, lab photos, "
            "main gate, server room, observer/conference room, UPS and generator, plus an optional "
            "walkthrough video), country/state/city, center category (School, University, ITI Diploma, "
            "ITI College, Degree College, Private Institute, Business School, Private Test Center, "
            "Engineering College, or Government Institution), nearby landmarks, wheelchair/lift "
            "accessibility, and distance from the nearest railway station, bus station, metro station, "
            "and airport. "
            "(2) Admin details - the center's point of contact, center superintendent details, IT "
            "manager details, and an emergency contact number. "
            "(3) Infrastructure details - number of labs and systems, network setup (single network "
            "or multiple, number of networks), whether each lab has partitions, air conditioning, a "
            "network printer, a projector, and a sound system, number of fire extinguishers per lab, "
            "free baggage storage space, drinking water availability, primary and secondary ISP "
            "details (provider, connection type such as Broadband/Lease line/Fibre Optics/Air Fibre, "
            "and speed), and generator/UPS backup capacity and duration. "
            "(4) Bank details - beneficiary name, bank name, account number, IFSC code, PAN number, "
            "GST number (if applicable) with GST state code, UIDAI number, and MSME number (if "
            "applicable). "
            "Before completing registration, the center must have these documents ready: a canceled "
            "cheque, GST certificate, Udyam certificate, PAN card, and (if available) a UIDAI number. "
            "Additional documents that can be uploaded include a signed agreement, MOU, and NDA. "
            "Registration cannot be completed without the required documents. "
            "To reset a forgotten M-Pin, use the 'Reset/Forgot MPIN' link on the Center Portal login "
            "page."
        ),
        "source_domain": "center.bookmytestcenter.com",
    },
    {
        "url": "https://clients.bookmytestcenter.com/",
        "title": "BMTC Client Portal - Verified Registration Flow (Assessment Companies)",
        "text": (
            "The Client Portal (clients.bookmytestcenter.com) is where an assessment company or "
            "client organization registers its account. On the live site this portal is labeled "
            "'Assessment Company'. The real registration flow, as implemented on the live site, is: "
            "Step 1 - Provide your full name, email, and phone number, and agree to the Privacy "
            "Policy and Terms & Conditions. "
            "Step 2 - Verify your phone number using a 6-digit OTP. "
            "Step 3 - Choose a 4-digit M-Pin for future logins. "
            "Step 4 - Enter company details across three sub-steps: "
            "(1) Company details - company name, company type (LLP, Private Limited, or Sole "
            "Proprietorship), company website, country/state/city/pincode, company address, and an "
            "uploaded company logo. "
            "(2) Point of Contact details - name of the coordinator, email, mobile number, an "
            "alternate mobile number, and a landline number. "
            "(3) Bank details and documents - bank name, account number, IFSC code, beneficiary name, "
            "PAN number, GST number, and uploaded documents including a canceled cheque, a signed "
            "agreement (with start and end dates), an NDA, an MOU, a GST certificate, a PAN document, "
            "and a Udyam certificate with Udyam Aadhar number. "
            "Step 5 - Once submitted, the account is activated ('Welcome to BookMyTestCenter, you are "
            "good to go') and the client is taken to their dashboard. "
            "After registration, per BMTC's published FAQ, assessment companies send their exam/test "
            "requirements to BMTC through this Client Portal or by contacting BMTC's sales/support "
            "team directly; BMTC then routes matching requests to appropriate test centers for "
            "confirmation and booking. "
            "To reset a forgotten M-Pin, use the 'Reset/Forgot MPin' link on the Client Portal login "
            "page. "
            "Note: as of the last verification of this content, the live Client Portal registration "
            "flow does not include self-service bulk candidate upload, CSV/PDF report generation, or "
            "custom exam-scheduling tools as part of the visible public registration flow — if the "
            "authenticated dashboard offers these, they are not reflected in this content and should "
            "not be assumed."
        ),
        "source_domain": "clients.bookmytestcenter.com",
    },
]


def get_seed_pages():
    return SEED_PAGES
