import smtplib
import os
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import logging

# Path to the email settings file, assuming it's in the root directory
EMAIL_SETTINGS_PATH = os.path.join(os.path.dirname(__file__), '..', 'email_settings.json')

# Set up logging
logging.basicConfig(filename='email.log', level=logging.DEBUG,
                    format='%(asctime)s - %(levelname)s - %(message)s')

def load_email_settings():
    """Load email settings from the JSON file."""
    if os.path.exists(EMAIL_SETTINGS_PATH):
        with open(EMAIL_SETTINGS_PATH, 'r') as f:
            return json.load(f)
    return {}

def send_email(to_email, subject, body, attachment_path=None, email_settings=None):
    """
    Sends an email using SMTP settings from a JSON file.

    Args:
        to_email (str or list): The recipient's email address or a list of addresses.
        subject (str): The subject of the email.
        body (str): The HTML body of the email.
        attachment_path (str, optional): The path to a file to attach. Defaults to None.
        email_settings (dict, optional): Pre-loaded email settings. Defaults to None.

    Returns:
        bool: True if the email was sent successfully, False otherwise.
    """
    logging.info(f"Attempting to send email to {to_email} with subject '{subject}'")
    if email_settings is None:
        email_settings = load_email_settings()
        logging.info("Loaded email settings from file.")

    sender_email = email_settings.get('email')
    password = email_settings.get('password')
    smtp_server = email_settings.get('smtp_server')
    smtp_port = email_settings.get('smtp_port')
    smtp_tls = email_settings.get('smtp_tls', True) # Default to True if not specified

    if not all([sender_email, password, smtp_server, smtp_port]):
        logging.error("Email settings are incomplete. Cannot send email.")
        print("Email settings are incomplete. Cannot send email.")
        return False

    if isinstance(to_email, str):
        to_email = [to_email]

    try:
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = ", ".join(to_email)
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'html'))

        if attachment_path:
            with open(attachment_path, 'rb') as attachment:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(attachment.read())
            encoders.encode_base64(part)
            part.add_header(
                'Content-Disposition',
                f'attachment; filename= {os.path.basename(attachment_path)}',
            )
            msg.attach(part)

        logging.info(f"Connecting to SMTP server {smtp_server}:{smtp_port}")
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.set_debuglevel(1) # Log SMTP conversation
            if smtp_tls:
                logging.info("Starting TLS...")
                server.starttls()
            logging.info("Logging in...")
            server.login(sender_email, password)
            logging.info("Sending email...")
            server.sendmail(sender_email, to_email, msg.as_string())
        logging.info(f"Email sent successfully to {', '.join(to_email)}")
        print(f"Email sent successfully to {', '.join(to_email)}")
        return True
    except smtplib.SMTPRecipientsRefused as e:
        logging.error(f"Error sending email: All recipients were refused. {e.recipients}")
        print(f"Error sending email: All recipients were refused. {e.recipients}")
        return False
    except Exception as e:
        logging.error(f"An error occurred while sending email: {e}")
        print(f"An error occurred while sending email: {e}")
        return False
