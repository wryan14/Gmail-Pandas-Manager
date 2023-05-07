# Gmail Pandas Manager

Gmail Pandas Manager is a Python-based tool that allows you to manage your Gmail account using the pandas library. With this tool, you can fetch, tag, classify, move, and delete your emails in a user-friendly and familiar pandas DataFrame interface.

## Features

- Fetch emails from your Gmail account
- Display emails in a pandas DataFrame
- Move emails to different folders/labels
- Delete emails in batch

## Installation

1. Clone this repository to your local machine:

`git clone https://github.com/yourusername/Gmail-Pandas-Manager.git`


2. Change to the project directory:

`cd Gmail-Pandas-Manager`

3. Install the required Python libraries:

`pip install -r requirements.txt`


## Setup

1. Follow the [Gmail API Python Quickstart](https://developers.google.com/gmail/api/quickstart/python) guide to enable the Gmail API and download the `credentials.json` file.

2. Place the `credentials.json` file in the project directory.

3. Run the `gmail_manager.py` script once to complete the OAuth 2.0 flow and generate the `token.json` file:

`python gmail_manager.py`


This will open a browser window for you to authenticate with your Google account and grant the necessary permissions.

4. Add the `credentials.json` and `token.json` files to your `.gitignore` to prevent accidentally pushing sensitive data to GitHub.

## Usage

To use Gmail Pandas Manager, you can import the `GmailManager` class in your Python script or notebook, create an instance, and then call the available methods to manage your Gmail account. Here's an example:

```python
from gmail_manager import GmailManager

gm = GmailManager()

# Fetch emails and display them as a DataFrame
emails_df = gm.fetch_emails()
print(emails_df)

# Move emails with specific IDs to a folder (e.g., 'Label_1')
gm.move_to_folder(['EMAIL_ID_1', 'EMAIL_ID_2'], 'Label_1')

# Delete emails with specific IDs
gm.delete_emails(['EMAIL_ID_3', 'EMAIL_ID_4'])
```