import os
import sys
import base64
import sqlite3
import pandas as pd
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

SCOPES = ['https://mail.google.com/']

class GmailManager:
    def __init__(self):
        self.creds = self.get_credentials()
        self.service = build('gmail', 'v1', credentials=self.creds)
        self.emails = None
        self.label_dict = self.get_labels()  
        self.conn = sqlite3.connect('emails.db')
        self.cursor = self.conn.cursor()
        self.create_table()

    def create_table(self):
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS emails (
                id TEXT PRIMARY KEY,
                subject TEXT,
                date TEXT,
                sender TEXT,
                labels TEXT
            )
        ''')
        self.conn.commit()

    def get_credentials(self):
        creds = None
        script_dir = os.path.dirname(os.path.abspath(sys.modules[self.__class__.__module__].__file__))
        project_dir = os.path.dirname(script_dir)
        credentials_dir = os.path.join(project_dir, 'credentials')
        token_path = os.path.join(credentials_dir, 'token.json')
        credentials_path = os.path.join(credentials_dir, 'credentials.json')

        if os.path.exists(token_path):
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
                creds = flow.run_local_server(port=0)
            with open(token_path, 'w') as token:
                token.write(creds.to_json())
        return creds

    def get_labels(self):
        labels = self.service.users().labels().list(userId='me').execute().get('labels', [])
        label_dict = {label['id']: label['name'] for label in labels}
        return label_dict

    def fetch_emails(self, query=''):
        try:
            self.cursor.execute("SELECT MAX(date) FROM emails")
            last_email_date = self.cursor.fetchone()[0]
            if last_email_date is not None:
                query += f' after:{last_email_date}'
        except sqlite3.OperationalError:
            pass

        next_page_token = None

        while True:
            result = self.service.users().messages().list(userId='me', q=query, pageToken=next_page_token).execute()
            messages = result.get('messages', [])

            for msg in messages:
                msg_data = self.service.users().messages().get(userId='me', id=msg['id'], format='full').execute()
                payload = msg_data['payload']
                headers = payload.get('headers')
                subject, date, sender, labels = None, None, None, None

                for header in headers:
                    header_name = header.get('name')
                    header_value = header.get('value')
                    if header_name == 'subject' or header_name == 'Subject':
                        subject = header_value
                    if header_name == 'Date' or header_name == 'date':
                        date = header_value
                    if header_name == 'From' or header_name == 'from':
                        sender = header_value

                label_ids = msg_data.get('labelIds', [])
                labels = [self.label_dict.get(label_id, label_id) for label_id in label_ids]

                email_data = {
                    'id': msg['id'],
                    'subject': subject,
                    'date': date,
                    'from': sender,
                    'labels': '; '.join(labels),
                }

                self.store_email(email_data)

            next_page_token = result.get('nextPageToken')
            if not next_page_token:
                break

        self.emails = self.get_emails_from_db()
        return self.emails

    
    def get_emails_from_db(self):
        self.cursor.execute('SELECT * FROM emails')
        rows = self.cursor.fetchall()
        df = pd.DataFrame(rows, columns=['id', 'subject', 'date', 'sender', 'labels'])
        return df

    def store_email(self, email_data):
        self.cursor.execute('''
            INSERT OR IGNORE INTO emails (id, subject, date, sender, labels)
            VALUES (:id, :subject, :date, :from, :labels)
        ''', email_data)
        self.conn.commit()

    def move_to_folder(self, email_df, folder_name):
        # Get the label ID for the folder
        folder = None
        labels = self.service.users().labels().list(userId='me').execute().get('labels', [])
        for label in labels:
            if label['name'] == folder_name:
                folder = label['id']
                break
        if not folder:
            print(f"Folder '{folder_name}' not found")
            return

        # Modify the messages to move them to the folder
        for email_id in email_df['id'].tolist():
            try:
                self.service.users().messages().modify(userId='me', id=email_id, body={'removeLabelIds': ['INBOX'], 'addLabelIds': [folder]}).execute()

                # Update the email record in the database
                with self.conn:
                    self.conn.execute(f"UPDATE emails SET labels = '{folder_name}' WHERE id = '{email_id}'")

            except HttpError as error:
                print(f'An error occurred moving email ID {email_id}: {error}')


        # Modify the messages to move them to the folder
        for email_id in email_df['id'].tolist():
            try:
                self.service.users().messages().modify(userId='me', id=email_id, body={'removeLabelIds': ['INBOX'], 'addLabelIds': [folder]}).execute()
            except HttpError as error:
                print(f'An error occurred moving email ID {email_id}: {error}')


    def delete_emails(self, email_df):
        for email_id in email_df['id'].tolist():
            try:
                self.service.users().messages().delete(userId='me', id=email_id).execute()
                self.cursor.execute('DELETE FROM emails WHERE id = ?', (email_id,))
                self.conn.commit()
            except HttpError as error:
                print(f'An error occurred deleting email ID {email_id}: {error}')


    def create_message(self, to, subject, message_text):
        """Create a message for an email.

        Args:
            to: Email address of the receiver.
            subject: The subject of the email message.
            message_text: The text of the email message.

        Returns:
            An object containing a base64url encoded email object.
        """
        message = MIMEText(message_text)
        message['to'] = to
        message['subject'] = subject
        encoded_message = base64.urlsafe_b64encode(message.as_bytes())
        return {'raw': encoded_message.decode()}

    def get_email_body(self, email_id):
        """Get the body of a specific email by its ID."""
        message = self.service.users().messages().get(userId='me', id=email_id, format='full').execute()

        try:
            body = message['payload']['parts'][0]['body']['data']
        except (KeyError, IndexError):
            try:
                body = message['payload']['body']['data']
            except (KeyError, IndexError):
                body = ""

        if not body:
            return ""
        else:
            text = base64.urlsafe_b64decode(body).decode('utf-8')
            return text
    
    def send_message(self, user_id, message):
        """Send an email message.

        Args:
            user_id: User's email address. The special value "me" can be used to indicate the authenticated user.
            message: Message to be sent.

        Returns:
            Sent Message.
        """
        try:
            message = (self.service.users().messages().send(userId=user_id, body=message).execute())
            print('Message Id: %s' % message['id'])
            return message
        except HttpError as error:
            print('An error occurred: %s' % error)

    def combine_and_forward_emails(self, email_df, forward_to, subject):
        """Combine and forward emails to another email address."""
        combined_body = ""

        for _, email in email_df.iterrows():
            combined_body += f"\n\n---------------------------------------------------\n"
            combined_body += f"From: {email['sender']}\n"
            combined_body += f"Subject: {email['subject']}\n"
            combined_body += f"Date: {email['date']}\n\n"
            combined_body += f"{self.get_email_body(email['id'])}"

        combined_body += "\n\n---------------------------------------------------\n"

        message = self.create_message(forward_to, subject, combined_body)
        self.send_message('me', message)
